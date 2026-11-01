"""Колесо: 20 секторов с множителями, один честный бросок на спин.

Сектор = floor(r · 20) для броска r игрока. У каждого риска сумма множителей 19,
то есть RTP 95% — как house_edge у остальных игр.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from .wallet import credit, debit, next_roll

# Порядок секторов по кругу — фронт рисует колесо ровно в этом порядке
WHEELS = {
    "low": [0, 1.2, 0, 1.5, 0, 1.2, 2, 0, 1.5, 1.2, 0, 3, 0, 1.2, 1.5, 0, 2, 1.2, 0, 1.5],
    "high": [0, 0, 3, 0, 0, 0, 5, 0, 0, 0, 3, 0, 0, 0, 8, 0, 0, 0, 0, 0],
}
MIN_BET = 100
MAX_BET = 10_000_000


class WheelError(Exception):
    pass


async def spin(s: AsyncSession, user_id: int, bet: int, risk: str, demo: bool) -> dict:
    if not MIN_BET <= bet <= MAX_BET:
        raise WheelError("Недопустимая ставка")
    if risk not in WHEELS:
        raise WheelError("Нет такого колеса")
    segments = WHEELS[risk]
    await debit(s, user_id, bet, "wheel_bet", risk, demo=demo)
    r, proof = await next_roll(s, user_id)
    index = int(r * len(segments))
    mult = segments[index]
    payout = int(bet * mult)
    if payout:
        await credit(s, user_id, payout, "wheel_win", risk, demo=demo)
    return {"index": index, "multiplier": mult, "payout": payout, "roll": r, "proof": proof}
