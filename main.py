"""Запуск: python main.py (настройки в .env, см. .env.example)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import TelegramObject

from finbot.config import load_config
from finbot.db import DB
from finbot.handlers import router


class AccessMiddleware(BaseMiddleware):
    """Пускает только пользователей из ALLOWED_USER_IDS и передаёт db в хендлеры."""

    def __init__(self, db: DB, allowed: set[int]):
        self.db, self.allowed = db, allowed

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("event_from_user")
        if self.allowed and (user is None or user.id not in self.allowed):
            return None
        data["db"] = self.db
        return await handler(event, data)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    db = DB(cfg.db_path)
    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    mw = AccessMiddleware(db, cfg.allowed_user_ids)
    dp.message.outer_middleware(mw)
    dp.callback_query.outer_middleware(mw)
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
