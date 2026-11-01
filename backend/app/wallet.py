"""Операции с балансом. Все изменения — атомарными UPDATE и с записью в журнал.
Функции не коммитят: транзакцию закрывает вызывающий код."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from . import fair
from .config import get_settings
from .models import DEMO_START, Transaction, User


class InsufficientFunds(Exception):
    pass


def coins(value: float) -> int:
    """Монеты -> сотые."""
    return round(value * 100)


async def get_or_create_user(
    s: AsyncSession, user_id: int, username: str | None = None, first_name: str = "", referrer_id: int | None = None
) -> User:
    user = await s.get(User, user_id)
    if user:
        if username is not None and (user.username != username or user.first_name != first_name):
            user.username, user.first_name = username, first_name
        return user
    if referrer_id == user_id or (referrer_id and not await s.get(User, referrer_id)):
        referrer_id = None
    seed = fair.new_seed()
    user = User(
        id=user_id,
        username=username,
        first_name=first_name or "",
        referrer_id=referrer_id,
        server_seed=seed,
        server_seed_hash=fair.sha256(seed),
        client_seed=fair.new_seed()[:16],
    )
    s.add(user)
    await s.flush()
    return user


def _col(demo: bool):
    """Колонка баланса: реальный или демо."""
    return User.demo_balance if demo else User.balance


async def credit(s: AsyncSession, user_id: int, amount: int, kind: str, ref: str | None = None,
                 demo: bool = False) -> None:
    col = _col(demo)
    await s.execute(update(User).where(User.id == user_id).values({col: col + amount}))
    s.add(Transaction(user_id=user_id, amount=amount, kind=kind, ref=ref, demo=demo))


async def debit(s: AsyncSession, user_id: int, amount: int, kind: str, ref: str | None = None,
                demo: bool = False) -> None:
    if amount <= 0:
        raise ValueError("amount must be positive")
    col = _col(demo)
    res = await s.execute(update(User).where(User.id == user_id, col >= amount).values({col: col - amount}))
    if res.rowcount != 1:
        raise InsufficientFunds
    s.add(Transaction(user_id=user_id, amount=-amount, kind=kind, ref=ref, demo=demo))


async def balance(s: AsyncSession, user_id: int, demo: bool = False) -> int:
    return (await s.execute(select(_col(demo)).where(User.id == user_id))).scalar_one()


async def refill_demo(s: AsyncSession, user_id: int) -> int:
    """Возвращает демо-баланс к стартовому — в демо деньги бесконечные."""
    await s.execute(update(User).where(User.id == user_id).values(demo_balance=DEMO_START))
    return DEMO_START


async def next_roll(s: AsyncSession, user_id: int) -> tuple[float, dict]:
    """Бросок для игрока с атомарным увеличением nonce. Возвращает (r, данные для проверки)."""
    row = (
        await s.execute(
            update(User)
            .where(User.id == user_id)
            .values(nonce=User.nonce + 1)
            .returning(User.server_seed, User.server_seed_hash, User.client_seed, User.nonce)
        )
    ).one()
    nonce = row.nonce - 1
    r = fair.roll(row.server_seed, row.client_seed, nonce)
    return r, {"server_seed_hash": row.server_seed_hash, "client_seed": row.client_seed, "nonce": nonce}


async def add_deposit_coins(s: AsyncSession, user_id: int, amount: int, kind: str, ref: str,
                            bonus_percent: float = 0) -> int:
    """Зачисление пополнения, бонуса к нему и реферального вознаграждения. Возвращает сумму бонуса."""
    await credit(s, user_id, amount, kind, ref)
    deposit_bonus = int(amount * bonus_percent / 100)
    if deposit_bonus > 0:
        await credit(s, user_id, deposit_bonus, "deposit_bonus", ref)
    await s.execute(update(User).where(User.id == user_id).values(total_deposit=User.total_deposit + amount))
    referrer_id = (await s.execute(select(User.referrer_id).where(User.id == user_id))).scalar_one()
    bonus = int(amount * get_settings().referral_percent / 100)
    if referrer_id and bonus > 0:
        await credit(s, referrer_id, bonus, "referral", f"{user_id}:{ref}")
        await s.execute(update(User).where(User.id == referrer_id).values(ref_earned=User.ref_earned + bonus))
    return deposit_bonus
