"""Provably fair: результаты считаются из секретного server seed (публикуется его хэш),
client seed игрока и nonce. После смены сида игрок может проверить все прошлые броски."""

import hashlib
import hmac
import math
import secrets


def new_seed() -> str:
    return secrets.token_hex(32)


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def roll(server_seed: str, client_seed: str, nonce: int) -> float:
    """Равномерное число в [0, 1)."""
    digest = hmac.new(server_seed.encode(), f"{client_seed}:{nonce}".encode(), hashlib.sha256).hexdigest()
    return int(digest[:13], 16) / 2**52


def crash_point(server_seed: str, house_edge: float) -> int:
    """Точка краша x100. P(краш >= m) = (1 - edge) / m."""
    digest = hmac.new(server_seed.encode(), b"crash", hashlib.sha256).hexdigest()
    x = int(digest[:13], 16) / 2**52
    return max(100, math.floor(100 * (1 - house_edge) / (1 - x)))


def pick_weighted(r: float, weights: list[int]) -> int:
    """Индекс по весам для броска r из [0, 1)."""
    target = r * sum(weights)
    acc = 0
    for i, w in enumerate(weights):
        acc += w
        if target < acc:
            return i
    return len(weights) - 1
