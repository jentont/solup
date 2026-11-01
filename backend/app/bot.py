import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (BusinessConnection, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           LabeledPrice, Message, PreCheckoutQuery, WebAppInfo)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from . import gifts
from .config import get_settings
from .db import Session
from .models import Deposit, InventoryItem, Item, Transaction, User, Withdrawal
from .wallet import add_deposit_coins, coins, credit, get_or_create_user

log = logging.getLogger(__name__)
router = Router()

MIN_STARS, MAX_STARS = 1, 100_000


def fmt(amount: int) -> str:
    return f"{amount / 100:,.2f}".replace(",", " ").rstrip("0").rstrip(".") + " 🪙"


def is_admin(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


def play_keyboard() -> InlineKeyboardMarkup | None:
    url = get_settings().webapp_url
    if not url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=url))]])


async def create_stars_link(bot: Bot, user_id: int, stars: int) -> str:
    if not MIN_STARS <= stars <= MAX_STARS:
        raise ValueError("Неверное количество звёзд")
    return await bot.create_invoice_link(
        title="Пополнение баланса",
        description=f"{stars} ⭐ → {fmt(int(stars * get_settings().coins_per_star * 100))}",
        payload=f"stars:{user_id}",
        currency="XTR",
        prices=[LabeledPrice(label="Пополнение", amount=stars)],
    )


# --- пользователи ---

@router.message(CommandStart())
async def start(message: Message, command: CommandObject) -> None:
    ref = None
    if command.args and command.args.startswith("ref_") and command.args[4:].isdigit():
        ref = int(command.args[4:])
    u = message.from_user
    async with Session() as s:
        user = await get_or_create_user(s, u.id, u.username, u.first_name or "", referrer_id=ref)
        await s.commit()
    await message.answer(
        f"Привет, {u.first_name}! 👋\n\nОткрывай кейсы, делай апгрейды и играй в краш. "
        f"Выигранные подарки можно вывести себе в Telegram.\n\nБаланс: {fmt(user.balance)}",
        reply_markup=play_keyboard())


@router.message(Command("balance"))
async def balance_cmd(message: Message) -> None:
    async with Session() as s:
        user = await s.get(User, message.from_user.id)
    await message.answer(f"Баланс: {fmt(user.balance if user else 0)}", reply_markup=play_keyboard())


# --- Telegram Stars ---

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    ok = query.currency == "XTR" and query.invoice_payload == f"stars:{query.from_user.id}"
    await query.answer(ok=ok, error_message=None if ok else "Платёж недоступен")


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    p = message.successful_payment
    if p.currency != "XTR":
        return
    amount = int(p.total_amount * get_settings().coins_per_star * 100)
    async with Session() as s:
        s.add(Deposit(user_id=message.from_user.id, method="stars", external_id=p.telegram_payment_charge_id,
                      asset="XTR", asset_amount=str(p.total_amount), coins=amount, status="paid"))
        try:
            await s.flush()
        except IntegrityError:
            return
        bonus = await add_deposit_coins(s, message.from_user.id, amount, "deposit_stars", p.telegram_payment_charge_id,
                                        get_settings().stars_bonus_percent)
        await s.commit()
    extra = f" + бонус {fmt(bonus)}" if bonus else ""
    await message.answer(f"✅ Зачислено {fmt(amount)}{extra}", reply_markup=play_keyboard())


# --- Подарки через Business-релеер ---

@router.business_connection()
async def business_connection(conn: BusinessConnection, bot: Bot) -> None:
    st = get_settings()
    if conn.user.id != st.relayer_user_id:
        log.warning("business connection от постороннего аккаунта %s", conn.user.id)
        return
    await gifts.set_connection_id(conn.id if conn.is_enabled else None)
    for admin in st.admin_ids:
        await bot.send_message(admin, f"Релеер {'подключён ✅' if conn.is_enabled else 'отключён ❌'}")


@router.business_message(F.gift | F.unique_gift)
async def business_gift(message: Message, bot: Bot) -> None:
    text = await gifts.handle_gift_message(bot, message)
    if text:
        try:
            await bot.send_message(message.from_user.id, text, reply_markup=play_keyboard())
        except Exception:
            log.info("не удалось уведомить %s о подарке", message.from_user.id)


async def notify_withdrawal(bot: Bot, withdrawal_id: int) -> None:
    async with Session() as s:
        w = await s.get(Withdrawal, withdrawal_id)
        inv = await s.get(InventoryItem, w.inventory_id)
        user = await s.get(User, w.user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Отправить", callback_data=f"wd:ok:{w.id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"wd:no:{w.id}"),
    ]])
    text = (f"📤 Вывод #{w.id}\n{inv.item.emoji} {inv.item.name} ({fmt(inv.item.value)})\n"
            f"Игрок: {user.first_name} @{user.username or '—'} ({user.id})\nДепозиты: {fmt(user.total_deposit)}")
    for admin in get_settings().admin_ids:
        await bot.send_message(admin, text, reply_markup=kb)


# --- Админка ---

@router.callback_query(F.data.startswith("wd:"))
async def withdrawal_decision(cb: CallbackQuery, bot: Bot) -> None:
    if not is_admin(cb.from_user.id):
        return
    _, action, wid = cb.data.split(":")
    try:
        if action == "ok":
            await cb.answer("Отправляю…")
            status = await gifts.process_withdrawal(bot, int(wid))
            async with Session() as s:
                w = await s.get(Withdrawal, int(wid))
            note = "✅ отправлен" if status == "done" else f"❌ ошибка: {w.error}"
        else:
            await gifts.reject_withdrawal(bot, int(wid))
            await cb.answer("Отклонено")
            note = "❌ отклонён"
    except gifts.GiftError as e:
        await cb.answer(str(e), show_alert=True)
        return
    await cb.message.edit_text(f"{cb.message.text}\n\n{note}")


@router.message(Command("stats"))
async def stats(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    async with Session() as s:
        users = (await s.execute(select(func.count(User.id)))).scalar_one()
        dep = (await s.execute(select(func.coalesce(func.sum(Deposit.coins), 0)).where(Deposit.status == "paid"))).scalar_one()
        balances = (await s.execute(select(func.coalesce(func.sum(User.balance), 0)))).scalar_one()
        owned = (await s.execute(select(func.coalesce(func.sum(Item.value), 0)).join(InventoryItem)
                                 .where(InventoryItem.status == "owned"))).scalar_one()
        withdrawn = (await s.execute(select(func.coalesce(func.sum(Item.value), 0)).join(InventoryItem)
                                     .where(InventoryItem.status == "withdrawn"))).scalar_one()
        pending = (await s.execute(select(func.count(Withdrawal.id)).where(Withdrawal.status == "pending"))).scalar_one()
    await message.answer(
        f"👥 Игроков: {users}\n💰 Пополнено: {fmt(dep)}\n🏦 На балансах: {fmt(balances)}\n"
        f"🎒 В инвентарях: {fmt(owned)}\n📤 Выведено: {fmt(withdrawn)}\n⏳ Заявок на вывод: {pending}\n"
        f"📈 Профит: {fmt(dep - balances - owned - withdrawn)}")


@router.message(Command("addbalance"))
async def add_balance(message: Message, command: CommandObject) -> None:
    if not is_admin(message.from_user.id):
        return
    try:
        uid, amount = command.args.split()
        uid, amount = int(uid), coins(float(amount))
    except (AttributeError, ValueError):
        await message.answer("Формат: /addbalance <user_id> <монеты> (можно отрицательное)")
        return
    async with Session() as s:
        if not await s.get(User, uid):
            await message.answer("Игрок не найден")
            return
        await credit(s, uid, amount, "admin", str(message.from_user.id))
        await s.commit()
    await message.answer(f"Готово: {fmt(amount)} игроку {uid}")


@router.message(Command("setprice"))
async def set_price(message: Message, command: CommandObject) -> None:
    """/setprice Plush Pepe | 600000 — задать цену коллекции (создаёт предмет, если его нет)."""
    if not is_admin(message.from_user.id):
        return
    try:
        name, value = (p.strip() for p in command.args.split("|"))
        value = coins(float(value))
    except (AttributeError, ValueError):
        await message.answer("Формат: /setprice <название коллекции> | <цена в монетах>")
        return
    async with Session() as s:
        item = (await s.execute(select(Item).where(Item.gift_name == name))).scalars().first()
        if item:
            item.value = value
        else:
            s.add(Item(name=name, gift_name=name, value=value))
        await s.commit()
    await message.answer(f"Цена «{name}»: {fmt(value)}\n⚠️ RTP кейсов с этим предметом изменился.")


@router.message(Command("withdrawals"))
async def list_withdrawals(message: Message, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return
    async with Session() as s:
        ids = (await s.execute(select(Withdrawal.id).where(Withdrawal.status == "pending")
                               .order_by(Withdrawal.id).limit(20))).scalars().all()
    if not ids:
        await message.answer("Заявок нет")
    for wid in ids:
        await notify_withdrawal(bot, wid)


@router.message(Command("stock"))
async def stock(message: Message, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return
    cid = await gifts.get_connection_id()
    if not cid:
        await message.answer("Релеер не подключён")
        return
    counts: dict[str, int] = {}
    offset = None
    while True:
        page = await bot.get_business_account_gifts(cid, exclude_unlimited=True, exclude_limited_upgradable=True,
                                                    exclude_limited_non_upgradable=True, offset=offset, limit=100)
        for g in page.gifts:
            if g.type == "unique":
                counts[g.gift.base_name] = counts.get(g.gift.base_name, 0) + 1
        if not page.next_offset:
            break
        offset = page.next_offset
    stars = await bot.get_business_account_star_balance(cid)
    lines = [f"{n}: {c}" for n, c in sorted(counts.items())] or ["пусто"]
    await message.answer("🎁 Склад релеера:\n" + "\n".join(lines) + f"\n\n⭐ Звёзд на релеере: {stars.amount}")


@router.message(Command("user"))
async def user_info(message: Message, command: CommandObject) -> None:
    if not is_admin(message.from_user.id) or not command.args or not command.args.isdigit():
        return
    async with Session() as s:
        user = await s.get(User, int(command.args))
        if not user:
            await message.answer("Не найден")
            return
        last = (await s.execute(select(Transaction).where(Transaction.user_id == user.id)
                                .order_by(Transaction.id.desc()).limit(10))).scalars().all()
    lines = [f"{t.created_at:%d.%m %H:%M} {t.kind} {fmt(t.amount)}" for t in last]
    await message.answer(f"{user.first_name} @{user.username or '—'}\nБаланс: {fmt(user.balance)}\n"
                         f"Депозиты: {fmt(user.total_deposit)}\n\n" + "\n".join(lines))


def create_bot() -> tuple[Bot, Dispatcher]:
    bot = Bot(get_settings().bot_token, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp
