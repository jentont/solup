"""Краш-игра: общий для всех раунд, множитель растёт экспоненциально до заранее определённой точки.
Точка краша фиксируется до приёма ставок; публикуется хэш сида, после краша — сам сид."""

import asyncio
import logging
import math
import time

from sqlalchemy import select, update

from . import fair
from .config import get_settings
from .db import Session
from .models import CrashBet, CrashRound, User
from .wallet import credit, debit

log = logging.getLogger(__name__)

BETTING_SECONDS = 8
PAUSE_SECONDS = 4
GROWTH = 0.07  # множитель = e^(GROWTH * секунды): x2 за ~10 с
TICK = 0.1
MIN_BET = 100  # 1 монета
MAX_BET = 10_000_000


class CrashError(Exception):
    pass


def now_ms() -> int:
    return int(time.time() * 1000)


def multiplier_at(elapsed_ms: int) -> int:
    """Множитель x100 через elapsed_ms после старта."""
    return math.floor(100 * math.exp(GROWTH * max(elapsed_ms, 0) / 1000))


class CrashEngine:
    def __init__(self) -> None:
        self.phase = "idle"  # betting | running | crashed
        self.round_id = 0
        self.seed_hash = ""
        self._seed = ""
        self._crash_point = 100
        self.betting_ends_at = 0
        self.started_at = 0
        self.last_point = 0
        self.bets: dict[int, dict] = {}
        self.history: list[int] = []
        self._subs: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    # --- подписки WebSocket ---
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subs.add(q)
        q.put_nowait(self.snapshot())
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def _broadcast(self, msg: dict) -> None:
        msg["now"] = now_ms()
        for q in list(self._subs):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                self._subs.discard(q)  # клиент не успевает читать — отключаем

    def _public_bets(self) -> list[dict]:
        return [{"user_id": uid, **b} for uid, b in self.bets.items()]

    def snapshot(self) -> dict:
        return {
            "type": "state",
            "now": now_ms(),
            "phase": self.phase,
            "round_id": self.round_id,
            "seed_hash": self.seed_hash,
            "betting_ends_at": self.betting_ends_at,
            "started_at": self.started_at,
            "crash_point": self.last_point if self.phase == "crashed" else None,
            "history": self.history[-20:],
            "bets": self._public_bets(),
        }

    def current_multiplier(self) -> int:
        return multiplier_at(now_ms() - self.started_at) if self.phase == "running" else 100

    # --- жизненный цикл ---
    async def start(self) -> None:
        await self._recover()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _recover(self) -> None:
        """Возврат ставок незавершённых раундов (после перезапуска)."""
        async with Session() as s:
            rounds = (await s.execute(select(CrashRound).where(CrashRound.status != "crashed"))).scalars().all()
            for rnd in rounds:
                bets = (await s.execute(
                    select(CrashBet).where(CrashBet.round_id == rnd.id, CrashBet.status == "active"))).scalars().all()
                for bet in bets:
                    bet.status = "refunded"
                    await credit(s, bet.user_id, bet.amount, "crash_refund", str(rnd.id), demo=bet.demo)
                rnd.status = "crashed"
            last = (await s.execute(
                select(CrashRound.crash_point).where(CrashRound.status == "crashed")
                .order_by(CrashRound.id.desc()).limit(20))).scalars().all()
            self.history = list(reversed(last))
            await s.commit()

    async def _run(self) -> None:
        while True:
            try:
                await self._round()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("crash round failed")
                await asyncio.sleep(2)

    async def _round(self) -> None:
        seed = fair.new_seed()
        point = fair.crash_point(seed, get_settings().house_edge)
        async with Session() as s:
            rnd = CrashRound(server_seed=seed, seed_hash=fair.sha256(seed), crash_point=point)
            s.add(rnd)
            await s.commit()
        async with self._lock:
            self.round_id, self.seed_hash, self._seed, self._crash_point = rnd.id, rnd.seed_hash, seed, point
            self.bets = {}
            self.phase = "betting"
            self.betting_ends_at = now_ms() + BETTING_SECONDS * 1000
        self._broadcast(self.snapshot())
        await asyncio.sleep(BETTING_SECONDS)

        async with self._lock:
            self.phase = "running"
            self.started_at = now_ms()
            async with Session() as s:
                await s.execute(update(CrashRound).where(CrashRound.id == self.round_id).values(status="running"))
                await s.commit()
        self._broadcast({"type": "start", "round_id": self.round_id, "started_at": self.started_at})

        while True:
            await asyncio.sleep(TICK)
            async with self._lock:
                m = self.current_multiplier()
                for uid, bet in self.bets.items():
                    auto = bet["auto_cashout"]
                    if bet["cashout_at"] is None and auto and auto <= m and auto < self._crash_point:
                        await self._cashout_locked(uid, auto)
                if m >= self._crash_point:
                    await self._crash_locked()
                    break
        await asyncio.sleep(PAUSE_SECONDS)

    async def _crash_locked(self) -> None:
        self.phase = "crashed"
        self.last_point = self._crash_point
        async with Session() as s:
            await s.execute(update(CrashBet).where(CrashBet.round_id == self.round_id, CrashBet.status == "active")
                            .values(status="lost"))
            await s.execute(update(CrashRound).where(CrashRound.id == self.round_id).values(status="crashed"))
            await s.commit()
        self.history = (self.history + [self._crash_point])[-50:]
        self._broadcast({"type": "crash", "round_id": self.round_id, "crash_point": self._crash_point,
                         "seed": self._seed, "seed_hash": self.seed_hash})

    # --- действия игроков ---
    async def place_bet(self, user_id: int, amount: int, auto_cashout: int | None, demo: bool = False) -> None:
        if not MIN_BET <= amount <= MAX_BET:
            raise CrashError("Недопустимая сумма ставки")
        if auto_cashout is not None and auto_cashout < 101:
            raise CrashError("Автовывод должен быть больше 1.00x")
        async with self._lock:
            if self.phase != "betting" or now_ms() >= self.betting_ends_at:
                raise CrashError("Приём ставок закрыт, дождитесь следующего раунда")
            if user_id in self.bets:
                raise CrashError("Ставка уже сделана")
            async with Session() as s:
                await debit(s, user_id, amount, "crash_bet", str(self.round_id), demo=demo)
                s.add(CrashBet(round_id=self.round_id, user_id=user_id, amount=amount, auto_cashout=auto_cashout,
                               demo=demo))
                name = (await s.execute(select(User.first_name).where(User.id == user_id))).scalar_one()
                await s.commit()
            self.bets[user_id] = {"name": name, "amount": amount, "auto_cashout": auto_cashout,
                                  "cashout_at": None, "payout": 0, "demo": demo}
        self._broadcast({"type": "bet", "user_id": user_id, **self.bets[user_id]})

    async def cashout(self, user_id: int) -> int:
        async with self._lock:
            if self.phase != "running":
                raise CrashError("Раунд не идёт")
            bet = self.bets.get(user_id)
            if not bet or bet["cashout_at"] is not None:
                raise CrashError("Нет активной ставки")
            m = self.current_multiplier()
            if m >= self._crash_point:
                raise CrashError("Не успели")
            return await self._cashout_locked(user_id, m)

    async def _cashout_locked(self, user_id: int, m: int) -> int:
        bet = self.bets[user_id]
        payout = bet["amount"] * m // 100
        async with Session() as s:
            res = await s.execute(
                update(CrashBet)
                .where(CrashBet.round_id == self.round_id, CrashBet.user_id == user_id, CrashBet.status == "active")
                .values(status="won", cashout_at=m, payout=payout))
            if res.rowcount != 1:
                raise CrashError("Нет активной ставки")
            await credit(s, user_id, payout, "crash_win", str(self.round_id), demo=bet["demo"])
            await s.commit()
        bet["cashout_at"], bet["payout"] = m, payout
        self._broadcast({"type": "cashout", "user_id": user_id, "cashout_at": m, "payout": payout})
        return payout


engine = CrashEngine()
