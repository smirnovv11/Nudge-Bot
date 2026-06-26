from __future__ import annotations

from datetime import datetime

from nudge_bot.reminders.domain import ReminderDeliveryAttempt
from nudge_bot.storage.unit_of_work import UnitOfWork


class ReminderDeliveryService:
    async def create_sending_attempt(
        self,
        uow: UnitOfWork,
        *,
        reminder_id: int,
        scheduled_for: datetime,
    ) -> ReminderDeliveryAttempt:
        attempt = await uow.attempts.create_sending(
            reminder_id=reminder_id,
            scheduled_for=scheduled_for,
        )
        return ReminderDeliveryAttempt(
            id=attempt.id,
            reminder_id=attempt.reminder_id,
            attempt_no=attempt.attempt_no,
        )

    async def mark_sent(
        self,
        uow: UnitOfWork,
        *,
        reminder_id: int,
        attempt_id: int,
        telegram_message_id: int,
        now: datetime,
    ) -> None:
        await uow.attempts.mark_sent(
            attempt_id=attempt_id,
            telegram_message_id=telegram_message_id,
            sent_at=now,
        )
        await uow.reminders.mark_delivery_sent(reminder_id=reminder_id, now=now)

    async def mark_failed(
        self,
        uow: UnitOfWork,
        *,
        reminder_id: int,
        attempt_id: int,
        error_code: str,
        error_message: str,
    ) -> None:
        await uow.attempts.mark_failed(
            attempt_id=attempt_id,
            error_code=error_code,
            error_message=error_message,
        )
        await uow.reminders.mark_delivery_failed(reminder_id=reminder_id)
