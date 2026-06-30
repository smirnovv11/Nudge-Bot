from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import AiogramError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nudge_bot.bot.keyboards import reminder_actions_keyboard
from nudge_bot.config import get_settings
from nudge_bot.reminders.domain import ReminderToSend
from nudge_bot.reminders.services import ReminderDeliveryService, ReminderSchedulerService
from nudge_bot.storage.database import create_engine, create_session_factory
from nudge_bot.storage.unit_of_work import unit_of_work

CLAIM_LIMIT = 50

scheduler_service = ReminderSchedulerService()
delivery_service = ReminderDeliveryService()


async def run_worker() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger(__name__)
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required to start the worker")

    bot = Bot(token=settings.bot_token)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    logger.info("worker: scheduler started")

    try:
        while True:
            await run_worker_tick(
                bot=bot,
                session_factory=session_factory,
                logger=logger,
                now=datetime.now(UTC),
            )
            await asyncio.sleep(settings.scheduler_poll_interval_seconds)
    finally:
        await bot.session.close()
        await engine.dispose()


async def run_worker_tick(
    *,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    logger: logging.Logger,
    now: datetime,
    limit: int = CLAIM_LIMIT,
) -> int:
    logger.debug("worker: scheduler tick")
    async with unit_of_work(session_factory) as uow:
        reminders = await scheduler_service.claim_due_reminders(uow, limit=limit, now=now)

    for reminder in reminders:
        await deliver_reminder(
            bot=bot,
            session_factory=session_factory,
            logger=logger,
            reminder=reminder,
            now=now,
        )

    return len(reminders)


async def deliver_reminder(
    *,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    logger: logging.Logger,
    reminder: ReminderToSend,
    now: datetime,
) -> None:
    async with unit_of_work(session_factory) as uow:
        attempt = await delivery_service.create_sending_attempt(
            uow,
            reminder_id=reminder.reminder_id,
            scheduled_for=reminder.due_at,
        )

    try:
        message = await bot.send_message(
            chat_id=reminder.telegram_user_id,
            text=f"⏰ <i>Reminder</i>\n\n📨 {reminder.reminder_text}",
            reply_markup=reminder_actions_keyboard(
                reminder_id=reminder.reminder_id,
                notification_id=attempt.id,
            ),
            parse_mode="HTML",
        )
    except AiogramError as exc:
        logger.warning(
            "worker: reminder delivery failed",
            extra={"reminder_id": reminder.reminder_id, "attempt_id": attempt.id},
        )
        async with unit_of_work(session_factory) as uow:
            await delivery_service.mark_failed(
                uow,
                reminder_id=reminder.reminder_id,
                attempt_id=attempt.id,
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
        return

    async with unit_of_work(session_factory) as uow:
        await delivery_service.mark_sent(
            uow,
            reminder_id=reminder.reminder_id,
            attempt_id=attempt.id,
            telegram_message_id=message.message_id,
            repeat_interval_minutes=reminder.repeat_interval_minutes,
            now=datetime.now(UTC),
        )


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
