"""Пополнение и вывод Telegram-подарков через аккаунт-релеер, подключённый к боту как Business-бот
(Настройки → Telegram для бизнеса → Чат-боты, с правами на подарки и звёзды)."""

import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .db import Session
from .models import KV, Deposit, InventoryItem, Item, Withdrawal
from .wallet import add_deposit_coins, get_or_create_user

log = logging.getLogger(__name__)

BC_KEY = "business_connection_id"


class GiftError(Exception):
    pass


async def get_connection_id() -> str | None:
    async with Session() as s:
        kv = await s.get(KV, BC_KEY)
        return kv.value if kv else None


async def set_connection_id(value: str | None) -> None:
    async with Session() as s:
        kv = await s.get(KV, BC_KEY)
        if value is None:
            if kv:
                await s.delete(kv)
        elif kv:
            kv.value = value
        else:
            s.add(KV(key=BC_KEY, value=value))
        await s.commit()


async def handle_gift_message(bot: Bot, message: Message) -> str | None:
    """Обрабатывает подарок, пришедший на релеер. Возвращает текст для пользователя."""
    sender = message.from_user
    if not sender or sender.id == get_settings().relayer_user_id:
        return None
    if message.unique_gift:
        info = message.unique_gift
        external_id = info.owned_gift_id or f"{message.chat.id}:{message.message_id}"
        base_name = info.gift.base_name
        async with Session() as s:
            await get_or_create_user(s, sender.id, sender.username, sender.first_name or "")
            item = (await s.execute(select(Item).where(Item.gift_name == base_name))).scalars().first()
            dep = Deposit(user_id=sender.id, method="gift", external_id=external_id, asset=base_name,
                          asset_amount=info.gift.name, coins=item.value if item else 0,
                          status="paid" if item else "unpriced")
            s.add(dep)
            try:
                await s.flush()
            except IntegrityError:
                return None  # повторное событие
            if item:
                await add_deposit_coins(s, sender.id, item.value, "deposit_gift", f"gift:{external_id}")
            await s.commit()
        if item:
            return f"🎁 Подарок {info.gift.name} принят: +{item.value / 100:g} 🪙"
        for admin in get_settings().admin_ids:
            await bot.send_message(admin, f"⚠️ Подарок без цены «{base_name}» ({info.gift.name}) от "
                                          f"{sender.id}. Задайте цену /setprice и начислите /addbalance.")
        return f"🎁 Подарок {info.gift.name} получен. Его стоимость проверит администратор и зачислит баланс."

    if message.gift:
        info = message.gift
        stars = info.convert_star_count or 0
        external_id = info.owned_gift_id or f"{message.chat.id}:{message.message_id}"
        amount = int(stars * get_settings().coins_per_star * 100)
        async with Session() as s:
            await get_or_create_user(s, sender.id, sender.username, sender.first_name or "")
            s.add(Deposit(user_id=sender.id, method="gift", external_id=external_id, asset="regular",
                          asset_amount=str(stars), coins=amount, status="paid" if amount else "unpriced"))
            try:
                await s.flush()
            except IntegrityError:
                return None
            if amount:
                await add_deposit_coins(s, sender.id, amount, "deposit_gift", f"gift:{external_id}")
            await s.commit()
        if info.owned_gift_id and message.business_connection_id:
            try:
                await bot.convert_gift_to_stars(message.business_connection_id, info.owned_gift_id)
            except Exception:
                log.warning("не удалось конвертировать подарок в звёзды", exc_info=True)
        return f"🎁 Подарок принят: +{amount / 100:g} 🪙" if amount else None
    return None


async def request_withdrawal(user_id: int, inventory_id: int) -> Withdrawal:
    async with Session() as s:
        inv = await s.get(InventoryItem, inventory_id)
        if not inv or inv.user_id != user_id or inv.status != "owned":
            raise GiftError("Предмет недоступен")
        if inv.demo:
            raise GiftError("Предметы из демо-режима вывести нельзя")
        if not inv.item.withdrawable or not inv.item.gift_name:
            raise GiftError("Этот предмет нельзя вывести")
        inv.status = "withdrawing"
        w = Withdrawal(user_id=user_id, inventory_id=inv.id)
        s.add(w)
        await s.commit()
        return w


async def _find_stock(bot: Bot, connection_id: str, base_name: str) -> tuple[str, int | None] | None:
    """Ищет на релеере свободный уникальный подарок нужной коллекции."""
    async with Session() as s:
        reserved = set((await s.execute(select(Withdrawal.owned_gift_id).where(
            Withdrawal.owned_gift_id.is_not(None), Withdrawal.status.in_(("processing", "done"))))).scalars())
    now = datetime.now(timezone.utc)
    offset = None
    while True:
        page = await bot.get_business_account_gifts(
            connection_id, exclude_unlimited=True, exclude_limited_upgradable=True,
            exclude_limited_non_upgradable=True, offset=offset, limit=100)
        for g in page.gifts:
            if g.type != "unique" or g.gift.base_name != base_name or g.owned_gift_id in reserved:
                continue
            if g.can_be_transferred is False:
                continue
            if g.next_transfer_date and g.next_transfer_date > now:
                continue
            return g.owned_gift_id, g.transfer_star_count
        if not page.next_offset:
            return None
        offset = page.next_offset


async def process_withdrawal(bot: Bot, withdrawal_id: int) -> str:
    """Пытается передать подарок пользователю. Возвращает статус: done | failed."""
    connection_id = await get_connection_id()
    async with Session() as s:
        # атомарный захват заявки, чтобы двойное нажатие не отправило подарок дважды
        res = await s.execute(update(Withdrawal).where(Withdrawal.id == withdrawal_id, Withdrawal.status == "pending")
                              .values(status="processing"))
        if res.rowcount != 1:
            raise GiftError("Заявка уже обработана")
        w = await s.get(Withdrawal, withdrawal_id)
        inv = await s.get(InventoryItem, w.inventory_id)
        base_name = inv.item.gift_name
        await s.commit()
    error = None
    if not connection_id:
        error = "Релеер не подключён"
    else:
        try:
            stock = await _find_stock(bot, connection_id, base_name)
            if not stock:
                error = f"Нет в наличии: {base_name}"
            else:
                owned_gift_id, fee = stock
                async with Session() as s:
                    w = await s.get(Withdrawal, withdrawal_id)
                    w.owned_gift_id = owned_gift_id
                    await s.commit()
                await bot.transfer_gift(connection_id, owned_gift_id, w.user_id, star_count=fee or None)
        except Exception as e:  # noqa: BLE001
            log.warning("ошибка вывода подарка", exc_info=True)
            error = str(e)[:500]
    async with Session() as s:
        w = await s.get(Withdrawal, withdrawal_id)
        inv = await s.get(InventoryItem, w.inventory_id)
        if error:
            w.status, w.error, w.owned_gift_id = "failed", error, None
            inv.status = "owned"  # предмет возвращается в инвентарь
        else:
            w.status, inv.status = "done", "withdrawn"
        await s.commit()
    if error:
        await bot.send_message(w.user_id, f"❌ Вывод «{base_name}» не удался, предмет возвращён в инвентарь.")
    else:
        await bot.send_message(w.user_id, f"✅ Подарок «{base_name}» отправлен вам!")
    return w.status


async def reject_withdrawal(bot: Bot, withdrawal_id: int) -> None:
    async with Session() as s:
        w = await s.get(Withdrawal, withdrawal_id)
        if not w or w.status != "pending":
            raise GiftError("Заявка уже обработана")
        inv = await s.get(InventoryItem, w.inventory_id)
        w.status, inv.status = "rejected", "owned"
        await s.commit()
    await bot.send_message(w.user_id, "Заявка на вывод отклонена, предмет возвращён в инвентарь.")
