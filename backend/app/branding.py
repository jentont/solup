"""Премиум-эмодзи из пака Solutions Winter и описание бота.

При запуске бот загружает пак (getStickerSet доступен любому боту) и запоминает,
какой custom_emoji_id соответствует каждому обычному эмодзи. pe("🎁") вернёт
<tg-emoji> из пака, а если такого эмодзи в паке нет — обычный символ.
Сообщения с pe() отправляются с parse_mode="HTML".
"""

import html
import logging

from aiogram import Bot
from aiogram.types import MenuButtonWebApp, WebAppInfo

from .config import get_settings

log = logging.getLogger(__name__)

_ids: dict[str, str] = {}

DESCRIPTION = (
    "🎁 SolUP — подарки Telegram, которые могут больше.\n\n"
    "📦 14 кейсов со всеми NFT-подарками\n"
    "🎮 Апгрейд, краш, мины, башня, колесо\n"
    "🎁 Бесплатный кейс каждый день\n"
    "🎮 Демо-режим — играй без риска\n"
    "💎 Пополнение: Stars, TON, USDT и подарки\n"
    "🎁 Вывод — настоящими подарками в Telegram\n\n"
    "Жми «Начать» 👇"
)
SHORT_DESCRIPTION = "Кейсы и мини-игры с NFT-подарками Telegram. Вывод — настоящими подарками. Есть демо без риска."


async def load_emoji(bot: Bot) -> None:
    pack = get_settings().emoji_pack
    if not pack:
        return
    try:
        st = await bot.get_sticker_set(pack)
    except Exception:
        log.warning("не удалось загрузить пак эмодзи %s", pack, exc_info=True)
        return
    for s in st.stickers:
        if s.emoji and s.custom_emoji_id:
            _ids.setdefault(s.emoji, s.custom_emoji_id)
            _ids.setdefault(s.emoji.replace("️", ""), s.custom_emoji_id)
    log.info("пак эмодзи %s: %d значков", pack, len(_ids))


def pe(ch: str) -> str:
    """Премиум-эмодзи из пака или обычный, если такого нет."""
    eid = _ids.get(ch) or _ids.get(ch.replace("️", ""))
    return f'<tg-emoji emoji-id="{eid}">{ch}</tg-emoji>' if eid else ch


def emoji_id(ch: str) -> str | None:
    """custom_emoji_id для иконки в кнопке (или None, если такого эмодзи нет в паке)."""
    return _ids.get(ch) or _ids.get(ch.replace("️", ""))


def esc(text: str) -> str:
    return html.escape(text or "")


async def set_profile(bot: Bot) -> None:
    """Описание бота (видно до «Начать»), короткое описание (в профиле) и кнопка «Играть» у поля ввода."""
    try:
        await bot.set_my_description(DESCRIPTION)
        await bot.set_my_short_description(SHORT_DESCRIPTION)
        if url := get_settings().webapp_url:
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Играть", web_app=WebAppInfo(url=url)))
    except Exception:
        log.warning("не удалось обновить описание бота", exc_info=True)
