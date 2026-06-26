from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from nudge_bot.bot.routers.reminders import router as reminders_router
from nudge_bot.bot.routers.start import router as start_router
from nudge_bot.config import get_settings
from nudge_bot.storage.database import create_engine, create_session_factory


async def run_bot() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required to start the Telegram bot")

    bot = Bot(token=settings.bot_token)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    dispatcher = Dispatcher()
    dispatcher.include_router(start_router)
    dispatcher.include_router(reminders_router)

    logging.getLogger(__name__).info("bot: polling started")
    try:
        await dispatcher.start_polling(
            bot,
            settings=settings,
            session_factory=session_factory,
        )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
