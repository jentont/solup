"""Проверка initData из Telegram Mini App."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

from .config import get_settings
from .db import Session
from .wallet import get_or_create_user

MAX_AGE = 24 * 3600


def validate_init_data(init_data: str, bot_token: str, max_age: int = MAX_AGE) -> dict:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        raise ValueError("no hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise ValueError("bad hash")
    if time.time() - int(pairs.get("auth_date", 0)) > max_age:
        raise ValueError("expired")
    return {**pairs, "user": json.loads(pairs.get("user", "{}"))}


async def resolve_user(authorization: str) -> int:
    st = get_settings()
    scheme, _, value = authorization.partition(" ")
    if scheme == "dev" and st.dev_auth and value.isdigit():
        tg_user = {"id": int(value), "first_name": f"Dev {value}", "username": None}
        start_param = None
    elif scheme == "tma":
        try:
            data = validate_init_data(value, st.bot_token)
        except ValueError:
            raise HTTPException(401, "Неверные данные авторизации")
        tg_user = data["user"]
        start_param = data.get("start_param")
    else:
        raise HTTPException(401, "Нет авторизации")
    ref = int(start_param[4:]) if start_param and start_param.startswith("ref_") and start_param[4:].isdigit() else None
    async with Session() as s:
        user = await get_or_create_user(s, tg_user["id"], tg_user.get("username"), tg_user.get("first_name", ""), ref)
        await s.commit()
    if user.is_banned:
        raise HTTPException(403, "Аккаунт заблокирован")
    return user.id


async def current_user(authorization: str = Header("")) -> int:
    return await resolve_user(authorization)
