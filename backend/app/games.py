"""Кейсы, апгрейд, продажа предметов, ежедневный бонус."""

from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from . import fair
from .config import get_settings
from .models import Case, InventoryItem, Item, Transaction, User, utcnow
from .wallet import coins, credit, debit, next_roll


class GameError(Exception):
    pass


async def open_case(s: AsyncSession, user_id: int, case_id: int, demo: bool = False) -> dict:
    case = await s.get(Case, case_id)
    if not case or not case.is_active or not case.items:
        raise GameError("Кейс недоступен")
    await debit(s, user_id, case.price, "case_open", str(case.id), demo=demo)
    r, proof = await next_roll(s, user_id)
    idx = fair.pick_weighted(r, [ci.weight for ci in case.items])
    item = case.items[idx].item
    inv = InventoryItem(user_id=user_id, item_id=item.id, source=f"case:{case.id}", demo=demo)
    s.add(inv)
    await s.flush()
    return {"inventory_id": inv.id, "item_id": item.id, "roll": r, "proof": proof}


def upgrade_chance(input_value: int, target_value: int) -> float:
    st = get_settings()
    if input_value <= 0 or target_value <= input_value:
        return 0.0
    return min(input_value / target_value * (1 - st.house_edge), st.upgrade_max_chance)


async def _lock_owned(s: AsyncSession, user_id: int, inventory_ids: list[int], new_status: str,
                      demo: bool = False) -> list[InventoryItem]:
    """Атомарно переводит предметы игрока из owned в new_status (защита от двойного использования).
    Демо-предметы и настоящие не смешиваются: берутся только предметы текущего режима."""
    ids = list(dict.fromkeys(inventory_ids))
    if not ids:
        return []
    res = await s.execute(
        update(InventoryItem)
        .where(InventoryItem.id.in_(ids), InventoryItem.user_id == user_id, InventoryItem.status == "owned",
               InventoryItem.demo == demo)
        .values(status=new_status)
    )
    if res.rowcount != len(ids):
        raise GameError("Предмет уже недоступен")
    rows = (await s.execute(select(InventoryItem).where(InventoryItem.id.in_(ids)))).scalars().all()
    for row in rows:
        await s.refresh(row)
    return list(rows)


async def upgrade(s: AsyncSession, user_id: int, inventory_ids: list[int], extra_balance: int, target_item_id: int,
                  demo: bool = False) -> dict:
    target = await s.get(Item, target_item_id)
    if not target:
        raise GameError("Предмет не найден")
    if extra_balance < 0:
        raise GameError("Неверная сумма")
    if not inventory_ids and extra_balance == 0:
        raise GameError("Выберите предметы или сумму")
    items = await _lock_owned(s, user_id, inventory_ids, "upgraded", demo)
    input_value = sum(i.item.value for i in items) + extra_balance
    chance = upgrade_chance(input_value, target.value)
    if chance <= 0:
        raise GameError("Цель должна быть дороже ставки")
    if extra_balance:
        await debit(s, user_id, extra_balance, "upgrade", str(target.id), demo=demo)
    r, proof = await next_roll(s, user_id)
    win = r < chance
    result = {"win": win, "chance": chance, "roll": r, "proof": proof, "inventory_id": None}
    if win:
        inv = InventoryItem(user_id=user_id, item_id=target.id, source="upgrade", demo=demo)
        s.add(inv)
        await s.flush()
        result["inventory_id"] = inv.id
    # запись в историю, даже если баланс не менялся (ставка только предметами)
    spent = ", ".join(i.item.name for i in items) or "баланс"
    s.add(Transaction(user_id=user_id, amount=0, kind="upgrade_win" if win else "upgrade_lose",
                      ref=f"{spent} → {target.name} ({chance:.1%})"[:128], demo=demo))
    return result


async def sell_items(s: AsyncSession, user_id: int, inventory_ids: list[int], demo: bool = False) -> int:
    items = await _lock_owned(s, user_id, inventory_ids, "sold", demo)
    total = sum(i.item.value for i in items)
    if total:
        await credit(s, user_id, total, "item_sell", ",".join(str(i.id) for i in items), demo=demo)
    return total


BONUS_PERIOD = timedelta(hours=24)


# Ежедневный бесплатный кейс: призы в монетах и их веса. Ожидание ≈ 10 монет в день.
DAILY_PRIZES: list[tuple[int, int]] = [(1, 300), (3, 250), (5, 200), (10, 120), (25, 80), (50, 35), (100, 12), (500, 3)]


async def claim_daily_case(s: AsyncSession, user_id: int) -> dict:
    """Открывает бесплатный кейс раз в сутки: приз выбирается честным броском игрока."""
    now = utcnow()
    res = await s.execute(
        update(User)
        .where(User.id == user_id, (User.last_bonus_at.is_(None)) | (User.last_bonus_at <= now - BONUS_PERIOD))
        .values(last_bonus_at=now)
    )
    if res.rowcount != 1:
        raise GameError("Кейс уже открыт, приходите позже")
    r, proof = await next_roll(s, user_id)
    index = fair.pick_weighted(r, [w for _, w in DAILY_PRIZES])
    amount = coins(DAILY_PRIZES[index][0])
    await credit(s, user_id, amount, "bonus")
    return {"amount": amount, "index": index, "proof": proof}


async def rotate_seed(s: AsyncSession, user_id: int, client_seed: str | None) -> dict:
    user = await s.get(User, user_id)
    await s.refresh(user)
    revealed = {"server_seed": user.server_seed, "server_seed_hash": user.server_seed_hash,
                "client_seed": user.client_seed, "nonces_used": user.nonce}
    seed = fair.new_seed()
    user.server_seed, user.server_seed_hash, user.nonce = seed, fair.sha256(seed), 0
    if client_seed:
        user.client_seed = client_seed[:64]
    return revealed
