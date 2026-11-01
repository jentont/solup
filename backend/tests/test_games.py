import asyncio
import hashlib
import hmac
import json
import time
from itertools import count
from urllib.parse import urlencode

import pytest
from sqlalchemy import select

from app import crash, fair, games
from app.auth import validate_init_data
from app.catalog import weights_for_rtp
from app.db import Session
from app.models import Case, InventoryItem, Item
from app.wallet import InsufficientFunds, add_deposit_coins, balance, coins, debit, get_or_create_user

_ids = count(1000)


async def new_user(money: float = 0, **kw) -> int:
    uid = next(_ids)
    async with Session() as s:
        await get_or_create_user(s, uid, "u", "User", **kw)
        if money:
            await add_deposit_coins(s, uid, coins(money), "test", "t")
        await s.commit()
    return uid


def test_roll_deterministic_and_uniform():
    rolls = [fair.roll("seed", "client", n) for n in range(20000)]
    assert rolls[:3] == [fair.roll("seed", "client", n) for n in range(3)]
    assert all(0 <= r < 1 for r in rolls)
    assert abs(sum(rolls) / len(rolls) - 0.5) < 0.01


def test_crash_point_distribution():
    edge = 0.05
    points = [fair.crash_point(fair.new_seed(), edge) for _ in range(40000)]
    assert min(points) >= 100
    for m in (200, 500):
        p = sum(pt >= m for pt in points) / len(points)
        assert abs(p - (1 - edge) * 100 / m) < 0.015


def test_case_weights_hit_rtp():
    values = [400, 900, 1500, 3000, 15000, 600000]
    w = weights_for_rtp(values, 1500, 0.9)
    ev = sum(a * b for a, b in zip(w, values)) / sum(w)
    assert abs(ev / 1500 - 0.9) < 0.01


async def test_seeded_cases_rtp():
    async with Session() as s:
        for case in (await s.execute(select(Case))).scalars():
            total = sum(ci.weight for ci in case.items)
            ev = sum(ci.weight * ci.item.value for ci in case.items) / total
            assert 0.85 < ev / case.price < 0.92, case.slug


async def test_debit_insufficient():
    uid = await new_user(5)
    async with Session() as s:
        with pytest.raises(InsufficientFunds):
            await debit(s, uid, coins(6), "x")
        await debit(s, uid, coins(5), "x")
        await s.commit()
        assert await balance(s, uid) == 0


async def test_referral_bonus():
    ref = await new_user()
    uid = await new_user(referrer_id=ref)
    async with Session() as s:
        await add_deposit_coins(s, uid, coins(100), "deposit_stars", "p1")
        await s.commit()
        assert await balance(s, ref) == coins(5)


async def test_open_case_and_sell():
    uid = await new_user(1000)
    async with Session() as s:
        case = (await s.execute(select(Case).where(Case.slug == "starter"))).scalar_one()
        res = await games.open_case(s, uid, case.id)
        await s.commit()
        assert await balance(s, uid) == coins(1000) - case.price
        inv = await s.get(InventoryItem, res["inventory_id"])
        value = inv.item.value
        sold = await games.sell_items(s, uid, [inv.id])
        await s.commit()
        assert sold == value
        with pytest.raises(games.GameError):
            await games.sell_items(s, uid, [inv.id])  # повторная продажа невозможна


async def test_upgrade_consumes_items():
    uid = await new_user(10000)
    async with Session() as s:
        cheap = (await s.execute(select(Item).order_by(Item.value))).scalars().first()
        target = (await s.execute(select(Item).where(Item.value > cheap.value * 3))).scalars().first()
        inv = InventoryItem(user_id=uid, item_id=cheap.id, source="test")
        s.add(inv)
        await s.commit()
        res = await games.upgrade(s, uid, [inv.id], 0, target.id)
        await s.commit()
        assert 0 < res["chance"] < 0.34
        await s.refresh(inv)
        assert inv.status == "upgraded"
        assert (res["inventory_id"] is not None) == res["win"]


async def test_fair_rotation_reveals_seed():
    uid = await new_user(1000)
    async with Session() as s:
        case = (await s.execute(select(Case).where(Case.slug == "starter"))).scalar_one()
        res = await games.open_case(s, uid, case.id)
        await s.commit()
        revealed = await games.rotate_seed(s, uid, "my-seed")
        await s.commit()
    assert fair.sha256(revealed["server_seed"]) == res["proof"]["server_seed_hash"]
    assert fair.roll(revealed["server_seed"], revealed["client_seed"], res["proof"]["nonce"]) == res["roll"]


async def test_daily_bonus_once():
    uid = await new_user()
    async with Session() as s:
        amount = await games.claim_daily_bonus(s, uid)
        await s.commit()
        assert amount > 0
        with pytest.raises(games.GameError):
            await games.claim_daily_bonus(s, uid)


def test_init_data_validation():
    token = "123:ABC"
    fields = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 1, "first_name": "A"})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    data = validate_init_data(urlencode(fields), token)
    assert data["user"]["id"] == 1
    with pytest.raises(ValueError):
        validate_init_data(urlencode(fields), "other:token")


async def test_crash_round_bet_and_cashout(monkeypatch):
    monkeypatch.setattr(crash, "BETTING_SECONDS", 0.3)
    monkeypatch.setattr(crash, "PAUSE_SECONDS", 0.1)
    monkeypatch.setattr(crash.fair, "crash_point", lambda seed, edge: 1000)  # 10x
    uid = await new_user(100)
    eng = crash.CrashEngine()
    await eng.start()
    try:
        for _ in range(50):
            if eng.phase == "betting":
                break
            await asyncio.sleep(0.02)
        await eng.place_bet(uid, coins(10), auto_cashout=None)
        with pytest.raises(crash.CrashError):
            await eng.place_bet(uid, coins(10), auto_cashout=None)
        while eng.phase != "running":
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.3)
        payout = await eng.cashout(uid)
        assert payout >= coins(10)
    finally:
        await eng.stop()
    async with Session() as s:
        assert await balance(s, uid) == coins(90) + payout


async def test_demo_mode_is_separate():
    from app import gifts
    from app.models import DEMO_START
    from app.wallet import refill_demo

    uid = await new_user(100)
    async with Session() as s:
        case = (await s.execute(select(Case).where(Case.slug == "starter"))).scalar_one()
        res = await games.open_case(s, uid, case.id, demo=True)
        await s.commit()
        # платили демо-монетами, настоящий баланс не тронут
        assert await balance(s, uid) == coins(100)
        assert await balance(s, uid, demo=True) == DEMO_START - case.price
        inv = await s.get(InventoryItem, res["inventory_id"])
        assert inv.demo
        # демо-предмет нельзя продать в реальном режиме
        with pytest.raises(games.GameError):
            await games.sell_items(s, uid, [inv.id], demo=False)
    with pytest.raises(gifts.GiftError):
        await gifts.request_withdrawal(uid, inv.id)
    async with Session() as s:
        sold = await games.sell_items(s, uid, [inv.id], demo=True)
        await s.commit()
        assert await balance(s, uid, demo=True) == DEMO_START - case.price + sold
        assert await balance(s, uid) == coins(100)
        await refill_demo(s, uid)
        await s.commit()
        assert await balance(s, uid, demo=True) == DEMO_START
