"""Точка входа для хостингов, которые запускают `python main.py`.

Поднимает сервер (API + Mini App + бот) на 0.0.0.0 и порту из переменной PORT (по умолчанию 8000).
"""

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
