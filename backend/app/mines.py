"""Мины: поле 5×5, игрок выбирает число мин и открывает клетки.

Расстановка мин честная: при старте берётся бросок игрока (nonce), и из его
server seed + client seed + nonce детерминированно тасуются 25 клеток.
Множитель после k безопасных клеток при m минах:
    (1 - edge) · Π (25 - i) / (25 - m - i), i = 0..k-1
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import fair
from .config import get_settings
from .models import MinesGame, User
from .wallet import credit, debit, next_roll

CELLS = 25
MIN_BET = 100  # 1 монета
MAX_BET = 10_000_000


class MinesError(Exception):
    pass


def multiplier(mines: int, opened: int) -> float:
    m = 1 - get_settings().house_edge
    for i in range(opened):
        m *= (CELLS - i) / (CELLS - mines - i)
    return m


def place_mines(server_seed: str, client_seed: str, nonce: int, mines: int) -> list[int]:
    cells = list(range(CELLS))
    for i in range(CELLS - 1, 0, -1):  # тасование Фишера — Йетса на бросках fair.roll
        j = int(fair.roll(server_seed, f"{client_seed}:{nonce}", i) * (i + 1))
        cells[i], cells[j] = cells[j], cells[i]
    return sorted(cells[:mines])


def _ints(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x]


def state(g: MinesGame | None) -> dict | None:
    if not g:
        return None
    opened = _ints(g.opened)
    over = g.status != "active"
    return {
        "id": g.id, "bet": g.bet, "mines": g.mines, "opened": opened, "status": g.status, "payout": g.payout,
        "multiplier": multiplier(g.mines, len(opened)),
        "next_multiplier": multiplier(g.mines, len(opened) + 1) if len(opened) < CELLS - g.mines else None,
        "mine_cells": _ints(g.board) if over else None,  # мины показываем только после конца игры
    }


async def active(s: AsyncSession, user_id: int, demo: bool) -> MinesGame | None:
    return (await s.execute(select(MinesGame).where(
        MinesGame.user_id == user_id, MinesGame.demo == demo, MinesGame.status == "active"))).scalars().first()


async def start(s: AsyncSession, user_id: int, bet: int, mines: int, demo: bool) -> MinesGame:
    if not MIN_BET <= bet <= MAX_BET:
        raise MinesError("Недопустимая ставка")
    if not 1 <= mines <= 24:
        raise MinesError("Мин может быть от 1 до 24")
    if await active(s, user_id, demo):
        raise MinesError("Сначала закончите текущую игру")
    await debit(s, user_id, bet, "mines_bet", None, demo=demo)
    _, proof = await next_roll(s, user_id)
    user = await s.get(User, user_id)
    await s.refresh(user)
    board = place_mines(user.server_seed, proof["client_seed"], proof["nonce"], mines)
    g = MinesGame(user_id=user_id, bet=bet, mines=mines, board=",".join(map(str, board)), opened="",
                  demo=demo, nonce=proof["nonce"])
    s.add(g)
    await s.flush()
    return g


async def open_cell(s: AsyncSession, user_id: int, cell: int, demo: bool) -> MinesGame:
    g = await active(s, user_id, demo)
    if not g:
        raise MinesError("Игра не начата")
    if not 0 <= cell < CELLS:
        raise MinesError("Нет такой клетки")
    opened = _ints(g.opened)
    if cell in opened:
        return g
    opened.append(cell)
    g.opened = ",".join(map(str, opened))
    if cell in _ints(g.board):
        g.status = "lost"
    elif len(opened) == CELLS - g.mines:  # открыты все безопасные клетки — забираем автоматически
        await _cashout(s, g)
    return g


async def _cashout(s: AsyncSession, g: MinesGame) -> None:
    opened = len(_ints(g.opened))
    g.payout = int(g.bet * multiplier(g.mines, opened))
    g.status = "cashed"
    await credit(s, g.user_id, g.payout, "mines_win", str(g.id), demo=g.demo)


async def cashout(s: AsyncSession, user_id: int, demo: bool) -> MinesGame:
    g = await active(s, user_id, demo)
    if not g:
        raise MinesError("Игра не начата")
    if not g.opened:
        raise MinesError("Откройте хотя бы одну клетку")
    await _cashout(s, g)
    return g
