"""Башня: 8 этажей, на каждом игрок выбирает одну ячейку из ряда. В части ячеек бомбы.

Сложность задаёт ширину ряда и число бомб на этаже. Расстановка честная:
из server seed + client seed + nonce броска при старте тасуются ячейки каждого этажа.
Множитель после k пройденных этажей:
    (1 - edge) · (cols / (cols - bombs)) ^ k
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import fair
from .config import get_settings
from .models import TowerGame, User
from .wallet import credit, debit, next_roll

FLOORS = 8
DIFFICULTIES = {"easy": (4, 1), "medium": (3, 1), "hard": (2, 1), "extreme": (3, 2)}  # ширина ряда, бомб
MIN_BET = 100
MAX_BET = 10_000_000


class TowerError(Exception):
    pass


def multiplier(difficulty: str, floors: int) -> float:
    cols, bombs = DIFFICULTIES[difficulty]
    return (1 - get_settings().house_edge) * (cols / (cols - bombs)) ** floors


def place_bombs(server_seed: str, client_seed: str, nonce: int, difficulty: str) -> list[list[int]]:
    cols, bombs = DIFFICULTIES[difficulty]
    board = []
    for floor in range(FLOORS):
        cells = list(range(cols))
        for i in range(cols - 1, 0, -1):  # Фишер — Йетс, у каждого этажа свои броски
            j = int(fair.roll(server_seed, f"{client_seed}:{nonce}", floor * 16 + i) * (i + 1))
            cells[i], cells[j] = cells[j], cells[i]
        board.append(sorted(cells[:bombs]))
    return board


def _board(g: TowerGame) -> list[list[int]]:
    return [[int(x) for x in f.split(",")] for f in g.board.split(";")]


def _picks(g: TowerGame) -> list[int]:
    return [int(x) for x in g.picks.split(",") if x]


def state(g: TowerGame | None) -> dict | None:
    if not g:
        return None
    picks = _picks(g)
    over = g.status != "active"
    passed = len(picks) - (g.status == "lost")
    cols, bombs = DIFFICULTIES[g.difficulty]
    return {
        "id": g.id, "bet": g.bet, "difficulty": g.difficulty, "cols": cols, "bombs": bombs, "floors": FLOORS,
        "picks": picks, "status": g.status, "payout": g.payout,
        "multiplier": multiplier(g.difficulty, passed),
        "next_multiplier": multiplier(g.difficulty, passed + 1) if not over and passed < FLOORS else None,
        "board": _board(g) if over else None,  # бомбы показываем только после конца игры
    }


async def active(s: AsyncSession, user_id: int, demo: bool) -> TowerGame | None:
    return (await s.execute(select(TowerGame).where(
        TowerGame.user_id == user_id, TowerGame.demo == demo, TowerGame.status == "active"))).scalars().first()


async def start(s: AsyncSession, user_id: int, bet: int, difficulty: str, demo: bool) -> TowerGame:
    if not MIN_BET <= bet <= MAX_BET:
        raise TowerError("Недопустимая ставка")
    if difficulty not in DIFFICULTIES:
        raise TowerError("Нет такой сложности")
    if await active(s, user_id, demo):
        raise TowerError("Сначала закончите текущую игру")
    await debit(s, user_id, bet, "tower_bet", None, demo=demo)
    _, proof = await next_roll(s, user_id)
    user = await s.get(User, user_id)
    await s.refresh(user)
    board = place_bombs(user.server_seed, proof["client_seed"], proof["nonce"], difficulty)
    g = TowerGame(user_id=user_id, bet=bet, difficulty=difficulty, picks="", demo=demo, nonce=proof["nonce"],
                  board=";".join(",".join(map(str, f)) for f in board))
    s.add(g)
    await s.flush()
    return g


async def pick(s: AsyncSession, user_id: int, col: int, demo: bool) -> TowerGame:
    g = await active(s, user_id, demo)
    if not g:
        raise TowerError("Игра не начата")
    cols, _ = DIFFICULTIES[g.difficulty]
    if not 0 <= col < cols:
        raise TowerError("Нет такой ячейки")
    picks = _picks(g)
    floor = len(picks)
    picks.append(col)
    g.picks = ",".join(map(str, picks))
    if col in _board(g)[floor]:
        g.status = "lost"
    elif len(picks) == FLOORS:  # вершина — забираем автоматически
        await _cashout(s, g)
    return g


async def _cashout(s: AsyncSession, g: TowerGame) -> None:
    g.payout = int(g.bet * multiplier(g.difficulty, len(_picks(g))))
    g.status = "cashed"
    await credit(s, g.user_id, g.payout, "tower_win", str(g.id), demo=g.demo)


async def cashout(s: AsyncSession, user_id: int, demo: bool) -> TowerGame:
    g = await active(s, user_id, demo)
    if not g:
        raise TowerError("Игра не начата")
    if not g.picks:
        raise TowerError("Пройдите хотя бы один этаж")
    await _cashout(s, g)
    return g
