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


async def test_daily_case_once():
    uid = await new_user()
    async with Session() as s:
        r = await games.claim_daily_case(s, uid)
        await s.commit()
        assert r["amount"] == coins(games.DAILY_PRIZES[r["index"]][0])
        assert await balance(s, uid) == r["amount"]
        with pytest.raises(games.GameError):
            await games.claim_daily_case(s, uid)


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


async def test_mines_flow():
    from app import mines

    uid = await new_user(100)
    async with Session() as s:
        g = await mines.start(s, uid, coins(10), 3, demo=False)
        await s.commit()
        board = [int(x) for x in g.board.split(",")]
        assert len(set(board)) == 3
        safe = [c for c in range(25) if c not in board]
        await mines.open_cell(s, uid, safe[0], False)
        await mines.open_cell(s, uid, safe[1], False)
        g = await mines.cashout(s, uid, False)
        await s.commit()
        assert g.status == "cashed" and g.payout > coins(10)
        assert await balance(s, uid) == coins(90) + g.payout
        # проигрыш: открыли мину — ставка сгорела
        g2 = await mines.start(s, uid, coins(10), 24, demo=False)
        await s.commit()
        mine = int(g2.board.split(",")[0])
        g2 = await mines.open_cell(s, uid, mine, False)
        await s.commit()
        assert g2.status == "lost"


async def test_tower_flow():
    from app import tower

    uid = await new_user(100)
    async with Session() as s:
        g = await tower.start(s, uid, coins(10), "medium", demo=False)
        await s.commit()
        board = [[int(x) for x in f.split(",")] for f in g.board.split(";")]
        assert len(board) == tower.FLOORS and all(len(f) == 1 for f in board)
        for floor in range(2):
            await tower.pick(s, uid, next(c for c in range(3) if c not in board[floor]), False)
        g = await tower.cashout(s, uid, False)
        await s.commit()
        assert g.status == "cashed" and g.payout == int(coins(10) * 0.95 * 1.5 ** 2)
        assert await balance(s, uid) == coins(90) + g.payout
        # проигрыш: выбрали бомбу на первом этаже
        g2 = await tower.start(s, uid, coins(10), "hard", demo=False)
        await s.commit()
        g2 = await tower.pick(s, uid, int(g2.board.split(";")[0]), False)
        await s.commit()
        assert g2.status == "lost" and tower.state(g2)["multiplier"] == 0.95


def test_wheel_rtp():
    from app import wheel

    for segments in wheel.WHEELS.values():
        assert len(segments) == 20 and abs(sum(segments) / 20 - 0.95) < 1e-9


async def test_wheel_spin():
    from app import wheel

    uid = await new_user(100)
    async with Session() as s:
        r = await wheel.spin(s, uid, coins(10), "low", demo=False)
        await s.commit()
        assert r["multiplier"] == wheel.WHEELS["low"][r["index"]]
        assert await balance(s, uid) == coins(90) + r["payout"]


def test_arcade_rtp():
    """Средний возврат каждой мгновенной игры — около 95% (рулетка 97,3%)."""
    import random as rnd

    from app import arcade

    rng = rnd.Random(7)
    params = {"dice": {"target": 50, "over": True}, "limbo": {"target": 3}, "coinflip": {"side": "heads"},
              "roulette": {"bet": "red"}, "plinko": {"risk": "high"}, "keno": {"picks": [1, 2, 3, 4, 5]},
              "slots": {}, "rps": {"move": "rock"}}
    for game, (fn, n) in arcade.INSTANT.items():
        runs = 200_000
        total = sum(fn([rng.random() for _ in range(n)], params[game])[0] for _ in range(runs)) / runs
        expected = 36 / 37 if game == "roulette" else 0.95
        assert abs(total - expected) < 0.03, (game, total)


def test_tables_exact_rtp():
    from math import comb

    from app import arcade

    probs = [comb(8, k) / 256 for k in range(9)]
    for risk, mults in arcade.PLINKO.items():
        assert 0.93 < sum(p * m for p, m in zip(probs, mults)) < 0.96, risk
    n, d = arcade.KENO_CELLS, arcade.KENO_DRAW
    for k, mults in arcade.KENO.items():
        ev = sum(comb(k, h) * comb(n - k, d - h) / comb(n, d) * m for h, m in enumerate(mults))
        assert 0.93 < ev < 0.96, k


async def test_arcade_play_and_rounds():
    from app import arcade

    uid = await new_user(1000)
    async with Session() as s:
        r = await arcade.play(s, uid, "coinflip", coins(10), {"side": "tails"}, demo=False)
        await s.commit()
        assert await balance(s, uid) == coins(990) + r["payout"]
        with pytest.raises(arcade.ArcadeError):
            await arcade.play(s, uid, "dice", coins(10), {"target": 99}, demo=False)
        assert await balance(s, uid) == coins(990) + r["payout"]  # неверные параметры — ставка не списана

        # Hi-Lo: идём по разложенной колоде и всегда угадываем, потом забираем
        g = await arcade.round_action(s, uid, "hilo", "start", coins(10), False)
        await s.commit()
        row = await arcade._active(s, uid, "hilo", False)
        deck = json.loads(row.state)["deck"]
        cur = deck[0]
        guess = "hi" if deck[1] >= cur else "lo"
        g = await arcade.round_action(s, uid, "hilo", guess, 0, False)
        assert g["status"] == "active" and g["steps"] == 1
        g = await arcade.round_action(s, uid, "hilo", "cashout", 0, False)
        await s.commit()
        assert g["status"] == "cashed" and g["payout"] == int(coins(10) * 0.95 / arcade.hilo_chance(cur, guess))

        # Блэкджек: доводим раздачу до конца, выплата из допустимых
        g = await arcade.round_action(s, uid, "blackjack", "start", coins(10), False)
        if g["status"] == "active":
            g = await arcade.round_action(s, uid, "blackjack", "stand", 0, False)
        await s.commit()
        assert g["status"] != "active" and g["payout"] in (0, coins(10), coins(20), coins(22))
        assert len(g["dealer"]) >= 2


def test_blackjack_values():
    from app.arcade import bj_value

    assert bj_value([1, 13]) == 21 and bj_value([1, 1, 9]) == 21 and bj_value([10, 12, 5]) == 25 and bj_value([1, 5, 10]) == 16
