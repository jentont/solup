"""Общее состояние процесса: экземпляр бота и живая лента выигрышей."""

import asyncio
from collections import deque

from aiogram import Bot

from .db import Session
from .models import User


class Runtime:
    def __init__(self) -> None:
        self.bot: Bot | None = None
        self.bot_username: str | None = None
        self.live: deque[dict] = deque(maxlen=30)
        self._subs: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    async def push_live(self, user_id: int, event: dict, delay: float = 0) -> None:
        """delay — чтобы лента не раскрывала результат раньше, чем закончится анимация у игрока."""
        if delay:
            asyncio.get_running_loop().call_later(
                delay, lambda: asyncio.ensure_future(self.push_live(user_id, event)))
            return
        async with Session() as s:
            name = (await s.get(User, user_id)).first_name or "Игрок"
        event = {"type": "live", "user": name[:16], **event}
        self.live.appendleft(event)
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                self._subs.discard(q)


runtime = Runtime()
