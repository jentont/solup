import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .bot import create_bot
from .catalog import seed_catalog
from .config import get_settings
from .crash import engine
from .cryptopay import cryptopay
from .db import Session, init_db
from .runtime import runtime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

WEBAPP_DIST = Path(__file__).resolve().parents[2] / "webapp" / "dist"


async def notify_crypto_paid(dep) -> None:
    if runtime.bot:
        try:
            await runtime.bot.send_message(dep.user_id, f"✅ Пополнение {dep.asset_amount} {dep.asset} зачислено: "
                                                        f"+{dep.coins / 100:g} 🪙")
        except Exception:
            log.info("не удалось уведомить %s", dep.user_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    st = get_settings()
    await init_db()
    async with Session() as s:
        await seed_catalog(s)
    await engine.start()
    tasks: list[asyncio.Task] = []
    if st.run_bot and st.bot_token:
        bot, dp = create_bot()
        runtime.bot = bot
        runtime.bot_username = (await bot.get_me()).username
        tasks.append(asyncio.create_task(
            dp.start_polling(bot, handle_signals=False, allowed_updates=dp.resolve_used_update_types())))
        log.info("бот @%s запущен", runtime.bot_username)
    else:
        log.warning("BOT_TOKEN не задан — бот не запущен, работает только API")
    if cryptopay.enabled:
        tasks.append(asyncio.create_task(cryptopay.poll_forever(notify_crypto_paid)))
    yield
    await engine.stop()
    for t in tasks:
        t.cancel()
    if runtime.bot:
        await runtime.bot.session.close()


app = FastAPI(title="Gift Casino", lifespan=lifespan)
app.include_router(router)

if WEBAPP_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEBAPP_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        file = (WEBAPP_DIST / path).resolve()
        ok = path and file.is_relative_to(WEBAPP_DIST) and file.is_file()
        return FileResponse(file if ok else WEBAPP_DIST / "index.html")
