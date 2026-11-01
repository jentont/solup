"""Пополнение TON/USDT через Crypto Pay API (@CryptoBot). Оплаченные счета проверяются опросом,
поэтому публичный webhook не нужен."""

import asyncio
import logging
import time
from decimal import Decimal

import aiohttp
from sqlalchemy import select

from .config import get_settings
from .db import Session
from .models import Deposit
from .wallet import add_deposit_coins

log = logging.getLogger(__name__)

ASSETS = ("TON", "USDT")
MIN_USD = Decimal("0.5")


class CryptoPayError(Exception):
    pass


class CryptoPay:
    def __init__(self) -> None:
        self._rates: dict[str, Decimal] = {}
        self._rates_at = 0.0

    @property
    def enabled(self) -> bool:
        return bool(get_settings().cryptopay_token)

    async def _call(self, method: str, **params) -> object:
        st = get_settings()
        base = "https://testnet-pay.crypt.bot/api/" if st.cryptopay_testnet else "https://pay.crypt.bot/api/"
        async with aiohttp.ClientSession() as http:
            async with http.post(base + method, json=params,
                                 headers={"Crypto-Pay-API-Token": st.cryptopay_token}) as resp:
                data = await resp.json()
        if not data.get("ok"):
            raise CryptoPayError(str(data.get("error")))
        return data["result"]

    async def usd_rate(self, asset: str) -> Decimal:
        """Курс актива в USD (кэш 5 минут)."""
        if asset == "USDT":
            return Decimal(1)
        if time.time() - self._rates_at > 300:
            try:
                rates = await self._call("getExchangeRates")
                self._rates = {r["source"]: Decimal(r["rate"]) for r in rates
                               if r["target"] == "USD" and r["is_valid"]}
                self._rates_at = time.time()
            except Exception:
                log.warning("не удалось получить курсы CryptoPay", exc_info=True)
        return self._rates.get(asset) or Decimal(str(get_settings().ton_usd_fallback))

    async def coins_for(self, asset: str, amount: Decimal) -> int:
        """Сколько сотых монеты дать за amount актива."""
        usd = amount * await self.usd_rate(asset)
        return int(usd * Decimal(str(get_settings().coins_per_usd)) * 100)

    async def create_invoice(self, user_id: int, asset: str, amount: Decimal) -> dict:
        if asset not in ASSETS:
            raise CryptoPayError("Неизвестный актив")
        if amount * await self.usd_rate(asset) < MIN_USD:
            raise CryptoPayError(f"Минимум ${MIN_USD}")
        inv = await self._call("createInvoice", asset=asset, amount=str(amount), payload=str(user_id),
                               description="Пополнение баланса", expires_in=3600)
        async with Session() as s:
            s.add(Deposit(user_id=user_id, method="crypto", external_id=str(inv["invoice_id"]),
                          asset=asset, asset_amount=str(amount)))
            await s.commit()
        return {"invoice_id": inv["invoice_id"],
                "url": inv.get("mini_app_invoice_url") or inv["bot_invoice_url"]}

    async def poll_forever(self, on_paid) -> None:
        while True:
            try:
                await self._poll_once(on_paid)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("ошибка опроса CryptoPay")
            await asyncio.sleep(15)

    async def _poll_once(self, on_paid) -> None:
        async with Session() as s:
            pending = (await s.execute(select(Deposit).where(Deposit.method == "crypto",
                                                             Deposit.status == "pending"))).scalars().all()
        if not pending:
            return
        by_id = {d.external_id: d for d in pending}
        result = await self._call("getInvoices", invoice_ids=",".join(by_id))
        for inv in result.get("items", []):
            dep = by_id.get(str(inv["invoice_id"]))
            if not dep or inv["status"] == "active":
                continue
            async with Session() as s:
                dep = await s.get(Deposit, dep.id)
                if dep.status != "pending":
                    continue
                if inv["status"] == "paid":
                    dep.coins = await self.coins_for(dep.asset, Decimal(inv["amount"]))
                    dep.status = "paid"
                    await add_deposit_coins(s, dep.user_id, dep.coins, "deposit_crypto", f"crypto:{dep.external_id}",
                                            get_settings().crypto_bonus_percent)
                else:
                    dep.status = "expired"
                await s.commit()
            if dep.status == "paid":
                await on_paid(dep)


cryptopay = CryptoPay()
