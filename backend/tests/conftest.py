import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_db = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db.as_posix()}"
os.environ["BOT_TOKEN"] = ""
os.environ["DEV_AUTH"] = "true"

import pytest_asyncio  # noqa: E402

from app.catalog import seed_catalog  # noqa: E402
from app.db import Session, init_db  # noqa: E402


@pytest_asyncio.fixture(autouse=True, loop_scope="session", scope="session")
async def db():
    await init_db()
    async with Session() as s:
        await seed_catalog(s)
    yield
