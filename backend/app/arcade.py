"""Мини-игры: восемь мгновенных (одна ставка — один честный результат) и две пошаговые (Hi-Lo, блэкджек).

Все броски — из сидов игрока, как в остальных играх: при ставке берётся nonce, и из
server seed + client seed + nonce выводится нужное число чисел fair.roll(…, i).
Пошаговые игры раскладывают колоду целиком при старте — смена сида посреди раздачи
ничего не меняет и не раскрывает будущие карты.

RTP ≈ 95% (1 − house_edge), кроме рулетки (европейская, 97,3%) и блэкджека (≈ 97% с выплатой 6:5).
"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import fair
from .config import get_settings
from .models import RoundGame, User
from .wallet import credit, debit, next_roll

MIN_BET = 100
MAX_BET = 10_000_000


class ArcadeError(Exception):
    pass


def _edge() -> float:
    return 1 - get_settings().house_edge


async def _rolls(s: AsyncSession, user_id: int, n: int) -> tuple[list[float], dict]:
    _, proof = await next_roll(s, user_id)
    user = await s.get(User, user_id)
    await s.refresh(user)
    seed = f"{proof['client_seed']}:{proof['nonce']}"
    return [fair.roll(user.server_seed, seed, i) for i in range(n)], proof


# --- таблицы выплат (фронт берёт их из GET /api/arcade) ---

PLINKO_ROWS = 8
PLINKO = {
    "low": [5.4, 2, 1.05, 0.96, 0.48, 0.96, 1.05, 2, 5.4],
    "high": [27, 3.8, 1.4, 0.3, 0.2, 0.3, 1.4, 3.8, 27],
}
KENO_CELLS, KENO_DRAW = 40, 10
KENO = {  # число выбранных → множитель за 0..k совпадений
    1: [0, 3.8],
    2: [0, 1.6, 5.8],
    3: [0, 1.1, 2.2, 13.5],
    4: [0, 0.5, 2, 6, 26],
    5: [0, 0.2, 1.4, 3.8, 15, 100],
}
SLOT_SYMBOLS = {"seven": 2, "diamond": 4, "bell": 6, "grape": 9, "lemon": 11, "cherry": 14}  # веса на барабане
SLOT_THREE = {"seven": 120, "diamond": 50, "bell": 20, "grape": 10, "lemon": 6, "cherry": 5}
SLOT_CHERRY = {2: 2, 1: 0.4}  # вишни не подряд: две или одна в любом месте
ROULETTE_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
ROULETTE_BETS = {"red": 2, "black": 2, "even": 2, "odd": 2, "low": 2, "high": 2, "zero": 36}
RPS = ["rock", "paper", "scissors"]


def tables() -> dict:
    return {"plinko": PLINKO, "plinko_rows": PLINKO_ROWS, "keno": KENO, "keno_cells": KENO_CELLS,
            "keno_draw": KENO_DRAW, "slots": {"three": SLOT_THREE, "cherry": SLOT_CHERRY},
            "roulette": ROULETTE_BETS, "edge": get_settings().house_edge}


def _pick(r: float, weights: dict[str, int]) -> str:
    return list(weights)[fair.pick_weighted(r, list(weights.values()))]


# --- мгновенные игры: (броски, параметры) → (множитель, детали для анимации) ---

def dice(rs, p):
    target, over = float(p.get("target", 50)), bool(p.get("over", True))
    if not 2 <= target <= 98:
        raise ArcadeError("Порог от 2 до 98")
    value = round(rs[0] * 100, 2)
    chance = (100 - target) / 100 if over else target / 100
    win = value > target if over else value < target
    return (_edge() / chance if win else 0), {"value": value}


def limbo(rs, p):
    target = round(float(p.get("target", 2)), 2)
    if not 1.01 <= target <= 1000:
        raise ArcadeError("Цель от ×1.01 до ×1000")
    result = max(1.0, int(_edge() / (1 - rs[0]) * 100) / 100)
    return (target if result >= target else 0), {"result": min(result, 1_000_000)}


def coinflip(rs, p):
    side = p.get("side")
    if side not in ("heads", "tails"):
        raise ArcadeError("Выберите сторону")
    landed = "heads" if rs[0] < 0.5 else "tails"
    return (2 * _edge() if landed == side else 0), {"landed": landed}


def roulette(rs, p):
    bet = p.get("bet")
    if bet not in ROULETTE_BETS:
        raise ArcadeError("Нет такой ставки")
    n = int(rs[0] * 37)
    win = {
        "zero": n == 0, "red": n in ROULETTE_RED, "black": n > 0 and n not in ROULETTE_RED,
        "even": n > 0 and n % 2 == 0, "odd": n % 2 == 1, "low": 1 <= n <= 18, "high": n >= 19,
    }[bet]
    return (ROULETTE_BETS[bet] if win else 0), {"number": n, "color": "green" if n == 0 else "red" if n in ROULETTE_RED else "black"}


def plinko(rs, p):
    risk = p.get("risk", "low")
    if risk not in PLINKO:
        raise ArcadeError("Нет такого риска")
    path = [int(r < 0.5) for r in rs[:PLINKO_ROWS]]  # 1 — шарик ушёл вправо
    slot = sum(path)
    return PLINKO[risk][slot], {"path": path, "slot": slot}


def keno(rs, p):
    picks = sorted(set(int(x) for x in p.get("picks", [])))
    if not 1 <= len(picks) <= max(KENO) or not all(1 <= x <= KENO_CELLS for x in picks):
        raise ArcadeError(f"Выберите от 1 до {max(KENO)} чисел")
    cells = list(range(1, KENO_CELLS + 1))
    for i in range(KENO_CELLS - 1, 0, -1):  # Фишер — Йетс, первые 10 — выпавшие
        j = int(rs[i] * (i + 1))
        cells[i], cells[j] = cells[j], cells[i]
    drawn = sorted(cells[:KENO_DRAW])
    hits = len(set(drawn) & set(picks))
    return KENO[len(picks)][hits], {"drawn": drawn, "hits": hits}


def slots(rs, p):
    reels = [_pick(r, SLOT_SYMBOLS) for r in rs[:3]]
    if len(set(reels)) == 1:
        mult = SLOT_THREE[reels[0]]
    else:
        mult = SLOT_CHERRY.get(reels.count("cherry"), 0)
    return mult, {"reels": reels}


def rps(rs, p):
    move = p.get("move")
    if move not in RPS:
        raise ArcadeError("Камень, ножницы или бумага")
    house = RPS[int(rs[0] * 3)]
    if house == move:
        return _edge(), {"house": house, "outcome": "draw"}
    win = RPS[(RPS.index(house) + 1) % 3] == move  # бумага бьёт камень и т. д.
    return (2 * _edge() if win else 0), {"house": house, "outcome": "win" if win else "lose"}


INSTANT = {"dice": (dice, 1), "limbo": (limbo, 1), "coinflip": (coinflip, 1), "roulette": (roulette, 1),
           "plinko": (plinko, PLINKO_ROWS), "keno": (keno, KENO_CELLS), "slots": (slots, 3), "rps": (rps, 1)}


async def play(s: AsyncSession, user_id: int, game: str, bet: int, params: dict, demo: bool) -> dict:
    if game not in INSTANT:
        raise ArcadeError("Нет такой игры")
    if not MIN_BET <= bet <= MAX_BET:
        raise ArcadeError("Недопустимая ставка")
    fn, n = INSTANT[game]
    fn([0.5] * n, params)  # проверка параметров до списания ставки
    await debit(s, user_id, bet, f"{game}_bet", None, demo=demo)
    rs, proof = await _rolls(s, user_id, n)
    mult, detail = fn(rs, params)
    payout = int(bet * mult)
    if payout:
        await credit(s, user_id, payout, f"{game}_win", None, demo=demo)
    return {"multiplier": round(mult, 4), "payout": payout, "detail": detail, "proof": proof}


# --- пошаговые игры: колода раскладывается при старте ---

DECK_SIZE = 52


def _card(r: float) -> int:
    return int(r * 13) + 1  # 1 — туз, 11..13 — валет, дама, король; бесконечная колода


async def _active(s: AsyncSession, user_id: int, game: str, demo: bool) -> RoundGame | None:
    return (await s.execute(select(RoundGame).where(
        RoundGame.user_id == user_id, RoundGame.game == game, RoundGame.demo == demo,
        RoundGame.status == "active"))).scalars().first()


async def _start(s: AsyncSession, user_id: int, game: str, bet: int, demo: bool) -> RoundGame:
    if not MIN_BET <= bet <= MAX_BET:
        raise ArcadeError("Недопустимая ставка")
    if await _active(s, user_id, game, demo):
        raise ArcadeError("Сначала закончите текущую игру")
    await debit(s, user_id, bet, f"{game}_bet", None, demo=demo)
    rs, proof = await _rolls(s, user_id, DECK_SIZE)
    g = RoundGame(user_id=user_id, game=game, bet=bet, demo=demo, nonce=proof["nonce"],
                  state=json.dumps({"deck": [_card(r) for r in rs], "next": 0}))
    s.add(g)
    await s.flush()
    return g


def _draw(st: dict) -> int:
    card = st["deck"][st["next"]]
    st["next"] += 1
    return card


async def _finish(s: AsyncSession, g: RoundGame, st: dict, payout: int, status: str) -> None:
    g.status, g.payout = status, payout
    g.state = json.dumps(st)
    if payout:
        await credit(s, g.user_id, payout, f"{g.game}_win", str(g.id), demo=g.demo)


# Hi-Lo: угадай, следующая карта старше-или-равна или младше-или-равна текущей.
# Множитель = (1 − edge) · Π 1/p угаданных шагов; забрать можно после первого угаданного.

def hilo_chance(card: int, guess: str) -> float:
    return (14 - card) / 13 if guess == "hi" else card / 13


async def hilo(s: AsyncSession, user_id: int, action: str, bet: int, demo: bool) -> RoundGame:
    if action == "start":
        g = await _start(s, user_id, "hilo", bet, demo)
        st = json.loads(g.state)
        st.update(cards=[_draw(st)], factor=1.0, steps=0)
        g.state = json.dumps(st)
        return g
    g = await _active(s, user_id, "hilo", demo)
    if not g:
        raise ArcadeError("Игра не начата")
    st = json.loads(g.state)
    if action == "cashout":
        if not st["steps"]:
            raise ArcadeError("Сделайте хотя бы один ход")
        await _finish(s, g, st, int(g.bet * _edge() * st["factor"]), "cashed")
        return g
    if action not in ("hi", "lo", "skip"):
        raise ArcadeError("Нет такого хода")
    if st["next"] >= DECK_SIZE - 1:
        raise ArcadeError("Колода закончилась — заберите выигрыш")
    cur, nxt = st["cards"][-1], _draw(st)
    st["cards"].append(nxt)
    if action != "skip":
        ok = nxt >= cur if action == "hi" else nxt <= cur
        if not ok:
            await _finish(s, g, st, 0, "lost")
            return g
        st["factor"] *= 1 / hilo_chance(cur, action)
        st["steps"] += 1
    g.state = json.dumps(st)
    return g


def hilo_state(g: RoundGame | None) -> dict | None:
    if not g:
        return None
    st = json.loads(g.state)
    cur = st["cards"][-1]
    mult = _edge() * st["factor"]
    return {"id": g.id, "bet": g.bet, "status": g.status, "payout": g.payout, "cards": st["cards"],
            "steps": st["steps"], "multiplier": mult if st["steps"] else 0,
            "hi": {"chance": hilo_chance(cur, "hi"), "multiplier": mult / hilo_chance(cur, "hi")},
            "lo": {"chance": hilo_chance(cur, "lo"), "multiplier": mult / hilo_chance(cur, "lo")}}


# Блэкджек: дилер добирает до 17, блэкджек платит 6:5, удвоение на первых двух картах, без сплита.

def bj_value(cards: list[int]) -> int:
    total = sum(min(c, 10) for c in cards)
    if 1 in cards and total + 10 <= 21:
        total += 10
    return total


async def blackjack(s: AsyncSession, user_id: int, action: str, bet: int, demo: bool) -> RoundGame:
    if action == "start":
        g = await _start(s, user_id, "blackjack", bet, demo)
        st = json.loads(g.state)
        st.update(player=[_draw(st)], dealer=[_draw(st)])
        st["player"].append(_draw(st))
        st["dealer"].append(_draw(st))
        st["doubled"] = False
        if bj_value(st["player"]) == 21 or bj_value(st["dealer"]) == 21:
            await _bj_settle(s, g, st)
        else:
            g.state = json.dumps(st)
        return g
    g = await _active(s, user_id, "blackjack", demo)
    if not g:
        raise ArcadeError("Игра не начата")
    st = json.loads(g.state)
    if action == "hit":
        st["player"].append(_draw(st))
        if bj_value(st["player"]) >= 21:
            await _bj_settle(s, g, st)
        else:
            g.state = json.dumps(st)
    elif action == "double":
        if len(st["player"]) != 2:
            raise ArcadeError("Удвоить можно только на первых двух картах")
        await debit(s, user_id, g.bet, "blackjack_bet", str(g.id), demo=demo)
        g.bet *= 2
        st["doubled"] = True
        st["player"].append(_draw(st))
        await _bj_settle(s, g, st)
    elif action == "stand":
        await _bj_settle(s, g, st)
    else:
        raise ArcadeError("Нет такого хода")
    return g


async def _bj_settle(s: AsyncSession, g: RoundGame, st: dict) -> None:
    p, d = st["player"], st["dealer"]
    pv = bj_value(p)
    p_bj = pv == 21 and len(p) == 2 and not st.get("doubled")
    d_bj = bj_value(d) == 21 and len(d) == 2
    if pv <= 21 and not p_bj and not d_bj:
        while bj_value(d) < 17:
            d.append(_draw(st))
    dv = bj_value(d)
    if p_bj and not d_bj:
        payout, outcome = int(g.bet * 2.2), "blackjack"
    elif pv > 21:
        payout, outcome = 0, "bust"
    elif d_bj and not p_bj:
        payout, outcome = 0, "lose"
    elif dv > 21 or pv > dv:
        payout, outcome = g.bet * 2, "win"
    elif pv == dv:
        payout, outcome = g.bet, "push"
    else:
        payout, outcome = 0, "lose"
    st["outcome"] = outcome
    await _finish(s, g, st, payout, "cashed" if payout else "lost")


def blackjack_state(g: RoundGame | None) -> dict | None:
    if not g:
        return None
    st = json.loads(g.state)
    over = g.status != "active"
    dealer = st["dealer"] if over else st["dealer"][:1]  # вторая карта дилера закрыта до конца
    return {"id": g.id, "bet": g.bet, "status": g.status, "payout": g.payout, "player": st["player"],
            "dealer": dealer, "player_value": bj_value(st["player"]), "dealer_value": bj_value(dealer),
            "can_double": not over and len(st["player"]) == 2, "outcome": st.get("outcome")}


ROUNDS = {"hilo": (hilo, hilo_state), "blackjack": (blackjack, blackjack_state)}


async def round_action(s: AsyncSession, user_id: int, game: str, action: str, bet: int, demo: bool) -> dict:
    if game not in ROUNDS:
        raise ArcadeError("Нет такой игры")
    fn, state = ROUNDS[game]
    return state(await fn(s, user_id, action, bet, demo))


async def round_get(s: AsyncSession, user_id: int, game: str, demo: bool) -> dict | None:
    if game not in ROUNDS:
        raise ArcadeError("Нет такой игры")
    return ROUNDS[game][1](await _active(s, user_id, game, demo))
