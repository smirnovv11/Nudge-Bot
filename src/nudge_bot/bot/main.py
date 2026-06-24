from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from nudge_bot.bot.routers.start import router as start_router
from nudge_bot.config import get_settings


async def run_bot() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required to start the Telegram bot")

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(start_router)

    logging.getLogger(__name__).info("bot: polling started")
    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
