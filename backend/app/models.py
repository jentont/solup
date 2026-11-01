from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


DEMO_START = 1_000_000  # стартовый демо-баланс: 10 000 монет (в сотых)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user id
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128), default="")
    balance: Mapped[int] = mapped_column(BigInteger, default=0)  # в сотых монеты
    demo_balance: Mapped[int] = mapped_column(BigInteger, default=DEMO_START, server_default=str(DEMO_START))
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    ref_earned: Mapped[int] = mapped_column(BigInteger, default=0)
    total_deposit: Mapped[int] = mapped_column(BigInteger, default=0)
    last_bonus_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Provably fair
    server_seed: Mapped[str] = mapped_column(String(64))
    server_seed_hash: Mapped[str] = mapped_column(String(64))
    client_seed: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[int] = mapped_column(Integer, default=0)


class Transaction(Base):
    """Журнал всех изменений баланса."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(32))
    ref: Mapped[str | None] = mapped_column(String(128))
    demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Item(Base):
    """Предмет, который можно выиграть. gift_name — base_name коллекционного подарка Telegram."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    gift_name: Mapped[str | None] = mapped_column(String(128), index=True)
    emoji: Mapped[str] = mapped_column(String(16), default="🎁")
    image_url: Mapped[str | None] = mapped_column(String(512))
    rarity: Mapped[str] = mapped_column(String(16), default="common")
    value: Mapped[int] = mapped_column(BigInteger)  # в сотых монеты
    withdrawable: Mapped[bool] = mapped_column(Boolean, default=True)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    emoji: Mapped[str] = mapped_column(String(16), default="📦")
    price: Mapped[int] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)

    items: Mapped[list["CaseItem"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class CaseItem(Base):
    __tablename__ = "case_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    weight: Mapped[int] = mapped_column(Integer)

    item: Mapped[Item] = relationship(lazy="selectin")


class InventoryItem(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    # owned | sold | upgraded | withdrawing | withdrawn
    status: Mapped[str] = mapped_column(String(16), default="owned", index=True)
    source: Mapped[str] = mapped_column(String(32))
    # предмет из демо-режима: продаётся только за демо-монеты, вывести нельзя
    demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    item: Mapped[Item] = relationship(lazy="selectin")


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory.id"), unique=True)
    # pending | done | failed | rejected
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    owned_gift_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Deposit(Base):
    """Пополнения из любых источников; external_id обеспечивает идемпотентность."""

    __tablename__ = "deposits"
    __table_args__ = (UniqueConstraint("method", "external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    method: Mapped[str] = mapped_column(String(16))  # stars | crypto | gift
    external_id: Mapped[str] = mapped_column(String(128))
    asset: Mapped[str | None] = mapped_column(String(16))
    asset_amount: Mapped[str | None] = mapped_column(String(32))
    # pending | paid | expired | unpriced
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    coins: Mapped[int] = mapped_column(BigInteger, default=0)
    note: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CrashRound(Base):
    __tablename__ = "crash_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_seed: Mapped[str] = mapped_column(String(64))
    seed_hash: Mapped[str] = mapped_column(String(64))
    crash_point: Mapped[int] = mapped_column(Integer)  # x100
    status: Mapped[str] = mapped_column(String(16), default="betting")  # betting | running | crashed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CrashBet(Base):
    __tablename__ = "crash_bets"
    __table_args__ = (UniqueConstraint("round_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("crash_rounds.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    auto_cashout: Mapped[int | None] = mapped_column(Integer)  # x100
    cashout_at: Mapped[int | None] = mapped_column(Integer)  # x100
    payout: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | won | lost | refunded
    demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class KV(Base):
    """Служебные значения (например, business_connection_id релеера)."""

    __tablename__ = "kv"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
