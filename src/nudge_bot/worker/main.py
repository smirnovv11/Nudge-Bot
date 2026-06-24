from __future__ import annotations

import asyncio
import logging

from nudge_bot.config import get_settings


async def run_worker() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("worker: scheduler started")

    while True:
        logger.debug("worker: scheduler tick")
        await asyncio.sleep(settings.scheduler_poll_interval_seconds)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
