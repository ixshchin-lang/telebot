from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    bot_token: str
    allowed_user_ids: set[int]
    db_path: str


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token.startswith("123456:"):
        raise SystemExit("Укажите BOT_TOKEN в файле .env (см. .env.example)")
    ids = {int(x) for x in os.getenv("ALLOWED_USER_IDS", "").replace(" ", "").split(",") if x}
    return Config(bot_token=token, allowed_user_ids=ids, db_path=os.getenv("DB_PATH", "data/finance.db"))
