from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    bot_token: str = ""
    admin_ids: list[int] = []
    # Аккаунт-релеер (Telegram Premium), подключённый к боту как Business-бот.
    # На него пользователи отправляют подарки, с него бот выводит подарки.
    relayer_user_id: int = 0
    relayer_username: str = ""
    webapp_url: str = ""  # публичный HTTPS-адрес Mini App (например, через cloudflared)

    # База
    database_url: str = f"sqlite+aiosqlite:///{(BACKEND_DIR / 'data.db').as_posix()}"

    # Экономика. Внутренняя валюта — монеты; суммы в базе хранятся в сотых (1 монета = 100).
    coins_per_star: float = 1.0
    coins_per_usd: float = 75.0
    ton_usd_fallback: float = 3.0  # если курс CryptoPay недоступен
    referral_percent: float = 5.0
    stars_bonus_percent: float = 10.0  # бонус сверху к пополнению Stars
    crypto_bonus_percent: float = 10.0  # бонус сверху к пополнению TON/USDT
    daily_bonus_min: int = 1
    daily_bonus_max: int = 25
    house_edge: float = 0.05  # для апгрейда и краша
    upgrade_max_chance: float = 0.75

    # Crypto Pay (@CryptoBot) — пополнение TON и USDT
    cryptopay_token: str = ""
    cryptopay_testnet: bool = False

    # Вывод подарков: True — без ручного подтверждения админом
    withdraw_auto: bool = False

    # Подвал Mini App: юзернейм поддержки (без @) и канал новостей
    support_username: str = ""
    news_channel: str = ""

    # Разработка: разрешает заголовок "Authorization: dev <user_id>" без initData
    dev_auth: bool = False
    run_bot: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
