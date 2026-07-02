from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nudge_bot.reminders.enums import ReminderDeliveryStatus
from nudge_bot.storage.models import ReminderAttempt


class ReminderAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_attempt_no(self, reminder_id: int) -> int:
        last_attempt_no = await self._session.scalar(
            select(func.max(ReminderAttempt.attempt_no)).where(
                ReminderAttempt.reminder_id == reminder_id
            )
        )
        return (last_attempt_no or 0) + 1

    async def create_sending(
        self,
        *,
        reminder_id: int,
        scheduled_for: datetime,
    ) -> ReminderAttempt:
        attempt = ReminderAttempt(
            reminder_id=reminder_id,
            attempt_no=await self.next_attempt_no(reminder_id),
            scheduled_for=scheduled_for,
            delivery_status=ReminderDeliveryStatus.SENDING,
        )
        self.add(attempt)
        await self._session.flush()
        return attempt

    async def get_by_id(self, attempt_id: int) -> ReminderAttempt | None:
        return await self._session.get(ReminderAttempt, attempt_id)

    async def mark_sent(
        self,
        *,
        attempt_id: int,
        telegram_message_id: int,
        sent_at: datetime,
    ) -> None:
        attempt = await self.get_by_id(attempt_id)
        if attempt is None:
            raise LookupError("reminder delivery attempt not found")
        attempt.delivery_status = ReminderDeliveryStatus.SENT
        attempt.telegram_message_id = telegram_message_id
        attempt.sent_at = sent_at
        attempt.next_retry_at = None

    async def mark_failed(
        self,
        *,
        attempt_id: int,
        error_code: str,
        error_message: str,
    ) -> None:
        attempt = await self.get_by_id(attempt_id)
        if attempt is None:
            raise LookupError("reminder delivery attempt not found")
        attempt.delivery_status = ReminderDeliveryStatus.FAILED
        attempt.error_code = error_code
        attempt.error_message = error_message
        attempt.next_retry_at = None

    def add(self, attempt: ReminderAttempt) -> None:
        self._session.add(attempt)
