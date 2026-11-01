import asyncio
import functools
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import time

from fastapi import APIRouter, Depends, Header, HTTPException, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from . import arcade, games, gifts, mines, tower, wheel
from .auth import current_user
from .bot import create_stars_link, notify_withdrawal
from .config import get_settings
from .crash import CrashError, engine
from .cryptopay import ASSETS, CryptoPayError, cryptopay
from .db import Session
from .models import Case, InventoryItem, Item, Transaction, User, Withdrawal, utcnow
from .runtime import runtime
from .wallet import InsufficientFunds, refill_demo

router = APIRouter(prefix="/api")


def demo_mode(x_demo: str = Header("0")) -> bool:
    """Режим игры из заголовка X-Demo: демо-баланс вместо настоящего."""
    return x_demo == "1"


def bal_of(u: User, demo: bool) -> int:
    return u.demo_balance if demo else u.balance


def item_dto(item: Item) -> dict:
    return {"id": item.id, "name": item.name, "emoji": item.emoji, "image_url": item.image_url,
            "rarity": item.rarity, "value": item.value, "withdrawable": item.withdrawable and bool(item.gift_name)}


def inv_dto(inv: InventoryItem) -> dict:
    return {"id": inv.id, "status": inv.status, "source": inv.source, "created_at": inv.created_at.isoformat(),
            "demo": inv.demo, "item": item_dto(inv.item)}


def game_errors(fn):
    """Переводит игровые исключения в HTTP 400."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except InsufficientFunds:
            raise HTTPException(400, "Недостаточно средств")
        except (games.GameError, CrashError, gifts.GiftError, CryptoPayError, mines.MinesError,
                tower.TowerError, wheel.WheelError, arcade.ArcadeError) as e:
            raise HTTPException(400, str(e))
    return wrapper


@router.get("/me")
async def me(uid: int = Depends(current_user)) -> dict:
    async with Session() as s:
        u = await s.get(User, uid)
        referrals = (await s.execute(select(User.id).where(User.referrer_id == uid))).scalars().all()
    bonus_at = u.last_bonus_at + games.BONUS_PERIOD if u.last_bonus_at else None
    return {
        "id": u.id, "first_name": u.first_name, "username": u.username, "balance": u.balance, "demo_balance": u.demo_balance,
        "ref_link": f"https://t.me/{runtime.bot_username}?start=ref_{u.id}" if runtime.bot_username else None,
        "referrals": len(referrals), "ref_earned": u.ref_earned, "referral_percent": get_settings().referral_percent,
        "bonus_available_at": bonus_at.isoformat() + "Z" if bonus_at else None,
        "fair": {"server_seed_hash": u.server_seed_hash, "client_seed": u.client_seed, "nonce": u.nonce},
    }


@router.get("/cases")
async def cases() -> list[dict]:
    async with Session() as s:
        rows = (await s.execute(select(Case).where(Case.is_active).order_by(Case.sort))).scalars().all()
    result = []
    for c in rows:
        total = sum(ci.weight for ci in c.items) or 1
        items = sorted(({**item_dto(ci.item), "chance": ci.weight / total} for ci in c.items),
                       key=lambda i: -i["value"])
        result.append({"id": c.id, "slug": c.slug, "name": c.name, "emoji": c.emoji, "price": c.price, "items": items})
    return result


@router.get("/items")
async def items() -> list[dict]:
    async with Session() as s:
        rows = (await s.execute(select(Item).order_by(Item.value))).scalars().all()
    return [item_dto(i) for i in rows]


class OpenCase(BaseModel):
    count: int = Field(1, ge=1, le=5)


@router.post("/cases/{case_id}/open")
@game_errors
async def open_case(case_id: int, body: OpenCase, uid: int = Depends(current_user),
                    demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        drops = [await games.open_case(s, uid, case_id, demo) for _ in range(body.count)]
        await s.commit()
        out = []
        for d in drops:
            inv = await s.get(InventoryItem, d["inventory_id"])
            out.append({**inv_dto(inv), "proof": d["proof"]})
        bal = bal_of(await s.get(User, uid), demo)
    for d in out if not demo else []:  # демо-выигрыши в живую ленту не попадают
        await runtime.push_live(uid, {"item": d["item"], "source": "case"}, delay=6)
    return {"drops": out, "balance": bal}


@router.get("/inventory")
async def inventory(uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> list[dict]:
    async with Session() as s:
        rows = (await s.execute(select(InventoryItem).where(InventoryItem.user_id == uid, InventoryItem.demo == demo,
                                                            InventoryItem.status.in_(("owned", "withdrawing")))
                                .order_by(InventoryItem.id.desc()))).scalars().all()
    return [inv_dto(i) for i in rows]


class Ids(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)


@router.post("/inventory/sell")
@game_errors
async def sell(body: Ids, uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        total = await games.sell_items(s, uid, body.ids, demo)
        await s.commit()
        bal = bal_of(await s.get(User, uid), demo)
    return {"sold": total, "balance": bal}


@router.post("/inventory/{inventory_id}/withdraw")
@game_errors
async def withdraw(inventory_id: int, uid: int = Depends(current_user)) -> dict:
    if not runtime.bot:
        raise HTTPException(503, "Бот не запущен")
    w = await gifts.request_withdrawal(uid, inventory_id)
    if get_settings().withdraw_auto:
        status = await gifts.process_withdrawal(runtime.bot, w.id)
    else:
        await notify_withdrawal(runtime.bot, w.id)
        status = "pending"
    return {"withdrawal_id": w.id, "status": status}


@router.get("/withdrawals")
async def withdrawals(uid: int = Depends(current_user)) -> list[dict]:
    async with Session() as s:
        rows = (await s.execute(select(Withdrawal, InventoryItem).join(InventoryItem)
                                .where(Withdrawal.user_id == uid).order_by(Withdrawal.id.desc()).limit(50))).all()
    return [{"id": w.id, "status": w.status, "created_at": w.created_at.isoformat(), "item": item_dto(inv.item)}
            for w, inv in rows]


class UpgradeBody(BaseModel):
    inventory_ids: list[int] = Field(default_factory=list, max_length=10)
    extra: int = Field(0, ge=0)
    target_item_id: int


@router.post("/upgrade")
@game_errors
async def upgrade(body: UpgradeBody, uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        res = await games.upgrade(s, uid, body.inventory_ids, body.extra, body.target_item_id, demo)
        await s.commit()
        res["balance"] = bal_of(await s.get(User, uid), demo)
        if res["win"]:
            inv = await s.get(InventoryItem, res["inventory_id"])
            res["item"] = item_dto(inv.item)
        if res["win"] and not demo:
            await runtime.push_live(uid, {"item": res["item"], "source": "upgrade",
                               "chance": res["chance"]}, delay=4.5)
    return res


@router.get("/upgrade/chance")
async def upgrade_chance(input_value: int, target_value: int) -> dict:
    return {"chance": games.upgrade_chance(input_value, target_value)}


class BetBody(BaseModel):
    amount: int = Field(gt=0)
    auto_cashout: int | None = None


@router.post("/crash/bet")
@game_errors
async def crash_bet(body: BetBody, uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    await engine.place_bet(uid, body.amount, body.auto_cashout, demo)
    return {"ok": True}


@router.post("/crash/cashout")
@game_errors
async def crash_cashout(uid: int = Depends(current_user)) -> dict:
    payout = await engine.cashout(uid)
    return {"payout": payout}


@router.websocket("/crash/ws")
async def crash_ws(ws: WebSocket) -> None:
    await ws.accept()
    q = engine.subscribe()
    try:
        while True:
            await ws.send_json(await q.get())
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        pass
    finally:
        engine.unsubscribe(q)


@router.get("/deposit/info")
async def deposit_info() -> dict:
    st = get_settings()
    relayer = (await gifts.get_relayer())[1]
    rates = {}
    if cryptopay.enabled:
        for a in ASSETS:
            rates[a] = float(await cryptopay.usd_rate(a)) * st.coins_per_usd
    return {
        "stars": {"enabled": runtime.bot is not None, "coins_per_star": st.coins_per_star,
                  "bonus_percent": st.stars_bonus_percent},
        "crypto": {"enabled": cryptopay.enabled, "coins_per_unit": rates, "bonus_percent": st.crypto_bonus_percent},
        "gifts": {"enabled": bool(relayer), "relayer": relayer},
    }


class StarsBody(BaseModel):
    stars: int = Field(ge=1, le=100_000)


@router.post("/deposit/stars")
async def deposit_stars(body: StarsBody, uid: int = Depends(current_user)) -> dict:
    if not runtime.bot:
        raise HTTPException(503, "Бот не запущен")
    return {"link": await create_stars_link(runtime.bot, uid, body.stars)}


class CryptoBody(BaseModel):
    asset: str
    amount: str


@router.post("/deposit/crypto")
@game_errors
async def deposit_crypto(body: CryptoBody, uid: int = Depends(current_user)) -> dict:
    if not cryptopay.enabled:
        raise HTTPException(503, "Криптопополнение не настроено")
    try:
        amount = Decimal(body.amount).quantize(Decimal("0.0001"))
    except InvalidOperation:
        raise HTTPException(400, "Неверная сумма")
    if amount <= 0:
        raise HTTPException(400, "Неверная сумма")
    return await cryptopay.create_invoice(uid, body.asset, amount)


@router.get("/bonus")
async def bonus_prizes() -> dict:
    total = sum(w for _, w in games.DAILY_PRIZES)
    return {"prizes": [{"amount": games.coins(a), "chance": w / total} for a, w in games.DAILY_PRIZES]}


@router.post("/bonus")
@game_errors
async def bonus(uid: int = Depends(current_user)) -> dict:
    async with Session() as s:
        r = await games.claim_daily_case(s, uid)
        await s.commit()
        bal = (await s.get(User, uid)).balance
    return {**r, "balance": bal}


class SeedBody(BaseModel):
    client_seed: str | None = Field(None, max_length=64)


@router.post("/fair/rotate")
async def rotate(body: SeedBody, uid: int = Depends(current_user)) -> dict:
    async with Session() as s:
        revealed = await games.rotate_seed(s, uid, body.client_seed)
        await s.commit()
    return revealed


@router.get("/history")
async def history(uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> list[dict]:
    async with Session() as s:
        rows = (await s.execute(select(Transaction).where(Transaction.user_id == uid, Transaction.demo == demo)
                                .order_by(Transaction.id.desc()).limit(50))).scalars().all()
    return [{"id": t.id, "amount": t.amount, "kind": t.kind, "created_at": t.created_at.isoformat(),
             "note": t.ref if t.kind.startswith("upgrade_") else None} for t in rows]


ONLINE_KINDS = {"cases": ("case_open",), "upgrade": ("upgrade", "upgrade_win", "upgrade_lose"),
                "crash": ("crash_bet",), "mines": ("mines_bet",),
                "tower": ("tower_bet",), "wheel": ("wheel_bet",),
                **{g: (f"{g}_bet",) for g in [*arcade.INSTANT, *arcade.ROUNDS]}}


@router.get("/online")
async def online() -> dict:
    """Сколько разных игроков играли в каждую игру за последние 15 минут."""
    since = utcnow() - timedelta(minutes=15)
    result = {}
    async with Session() as s:
        for game, kinds in ONLINE_KINDS.items():
            result[game] = (await s.execute(
                select(func.count(func.distinct(Transaction.user_id)))
                .where(Transaction.kind.in_(kinds), Transaction.created_at >= since, Transaction.demo.is_(False))
            )).scalar_one()
    result["crash"] = max(result["crash"], sum(1 for b in engine.bets.values() if not b["demo"]))
    return result


@router.get("/config")
async def app_config() -> dict:
    st = get_settings()
    return {"bot_username": runtime.bot_username, "support": st.support_username or None,
            "news": st.news_channel or None}


class MinesStart(BaseModel):
    bet: int = Field(gt=0)
    mines: int = Field(ge=1, le=24)


class MinesOpen(BaseModel):
    cell: int = Field(ge=0, le=24)


async def _mines_reply(s, uid: int, demo: bool, g) -> dict:
    return {"game": mines.state(g), "balance": bal_of(await s.get(User, uid), demo)}


@router.get("/mines")
async def mines_get(uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        return await _mines_reply(s, uid, demo, await mines.active(s, uid, demo))


@router.post("/mines/start")
@game_errors
async def mines_start(body: MinesStart, uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        g = await mines.start(s, uid, body.bet, body.mines, demo)
        await s.commit()
        return await _mines_reply(s, uid, demo, g)


@router.post("/mines/open")
@game_errors
async def mines_open(body: MinesOpen, uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        g = await mines.open_cell(s, uid, body.cell, demo)
        await s.commit()
        return await _mines_reply(s, uid, demo, g)


@router.post("/mines/cashout")
@game_errors
async def mines_cashout(uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        g = await mines.cashout(s, uid, demo)
        await s.commit()
        return await _mines_reply(s, uid, demo, g)


class TowerStart(BaseModel):
    bet: int = Field(gt=0)
    difficulty: str


class TowerPick(BaseModel):
    col: int = Field(ge=0, le=3)


async def _tower_reply(s, uid: int, demo: bool, g) -> dict:
    return {"game": tower.state(g), "balance": bal_of(await s.get(User, uid), demo)}


@router.get("/tower")
async def tower_get(uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        return await _tower_reply(s, uid, demo, await tower.active(s, uid, demo))


@router.post("/tower/start")
@game_errors
async def tower_start(body: TowerStart, uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        g = await tower.start(s, uid, body.bet, body.difficulty, demo)
        await s.commit()
        return await _tower_reply(s, uid, demo, g)


@router.post("/tower/pick")
@game_errors
async def tower_pick(body: TowerPick, uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        g = await tower.pick(s, uid, body.col, demo)
        await s.commit()
        return await _tower_reply(s, uid, demo, g)


@router.post("/tower/cashout")
@game_errors
async def tower_cashout(uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        g = await tower.cashout(s, uid, demo)
        await s.commit()
        return await _tower_reply(s, uid, demo, g)


@router.get("/wheel")
async def wheel_info() -> dict:
    return {"wheels": wheel.WHEELS}


class WheelSpin(BaseModel):
    bet: int = Field(gt=0)
    risk: str


@router.post("/wheel/spin")
@game_errors
async def wheel_spin(body: WheelSpin, uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        r = await wheel.spin(s, uid, body.bet, body.risk, demo)
        await s.commit()
        return {**r, "balance": bal_of(await s.get(User, uid), demo)}


@router.get("/arcade")
async def arcade_tables() -> dict:
    return arcade.tables()


class PlayBody(BaseModel):
    bet: int = Field(gt=0)
    params: dict = Field(default_factory=dict)


@router.post("/play/{game}")
@game_errors
async def play(game: str, body: PlayBody, uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        r = await arcade.play(s, uid, game, body.bet, body.params, demo)
        await s.commit()
        return {**r, "balance": bal_of(await s.get(User, uid), demo)}


class RoundBody(BaseModel):
    action: str
    bet: int = 0


@router.get("/round/{game}")
@game_errors
async def round_get(game: str, uid: int = Depends(current_user), demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        return {"game": await arcade.round_get(s, uid, game, demo), "balance": bal_of(await s.get(User, uid), demo)}


@router.post("/round/{game}")
@game_errors
async def round_act(game: str, body: RoundBody, uid: int = Depends(current_user),
                    demo: bool = Depends(demo_mode)) -> dict:
    async with Session() as s:
        g = await arcade.round_action(s, uid, game, body.action, body.bet, demo)
        await s.commit()
        return {"game": g, "balance": bal_of(await s.get(User, uid), demo)}


@router.post("/demo/refill")
async def demo_refill(uid: int = Depends(current_user)) -> dict:
    async with Session() as s:
        bal = await refill_demo(s, uid)
        await s.commit()
    return {"balance": bal}


_avatars: dict[int, tuple[float, bytes | None]] = {}
AVATAR_TTL = 3600


@router.get("/avatar/{user_id}")
async def avatar(user_id: int) -> Response:
    """Фото профиля Telegram через бота (photo_url в initData приходит не во всех клиентах). Кэш на час."""
    cached = _avatars.get(user_id)
    if not cached or time.time() - cached[0] > AVATAR_TTL:
        data = None
        if runtime.bot:
            try:
                photos = await runtime.bot.get_user_profile_photos(user_id, limit=1)
                if photos.photos:
                    size = photos.photos[0][-1] if len(photos.photos[0]) < 3 else photos.photos[0][1]  # ~320px
                    data = (await runtime.bot.download(size.file_id)).read()
            except Exception:
                data = None
        cached = _avatars[user_id] = (time.time(), data)
    if not cached[1]:
        raise HTTPException(404, "Нет фото")
    return Response(cached[1], media_type="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/live")
async def live() -> list[dict]:
    return list(runtime.live)


@router.websocket("/ws")
async def user_ws(ws: WebSocket) -> None:
    """Общий канал: живая лента выигрышей."""
    await ws.accept()
    q = runtime.subscribe()
    try:
        while True:
            await ws.send_json(await q.get())
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        pass
    finally:
        runtime.unsubscribe(q)

