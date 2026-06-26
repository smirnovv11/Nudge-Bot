from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nudge_bot.reminders.domain import ReminderResult
from nudge_bot.reminders.enums import ReminderStatus
from nudge_bot.storage.unit_of_work import UnitOfWork


class ReminderActionService:
    async def mark_completed(
        self,
        uow: UnitOfWork,
        *,
        reminder_id: int,
        user_id: int,
        now: datetime | None = None,
    ) -> ReminderResult:
        now = now or datetime.now(UTC)
        reminder = await uow.reminders.get_by_id_for_user(
            reminder_id=reminder_id,
            user_id=user_id,
        )

        if reminder is None:
            raise LookupError("reminder not found")

        if reminder.status == ReminderStatus.COMPLETED:
            return ReminderResult(
                reminder_id=reminder_id,
                status=ReminderStatus.COMPLETED,
                changed=False,
            )

        reminder.status = ReminderStatus.COMPLETED
        reminder.completed_at = now
        reminder.locked_at = None

        return ReminderResult(
            reminder_id=reminder_id,
            status=ReminderStatus.COMPLETED,
            changed=True,
        )

    async def snooze(
        self,
        uow: UnitOfWork,
        *,
        reminder_id: int,
        user_id: int,
        interval_minutes: int,
        now: datetime | None = None,
    ) -> ReminderResult:
        now = now or datetime.now(UTC)
        reminder = await uow.reminders.get_by_id_for_user(
            reminder_id=reminder_id,
            user_id=user_id,
        )

        if reminder is None:
            raise LookupError("reminder not found")

        if reminder.status == ReminderStatus.COMPLETED:
            return ReminderResult(
                reminder_id=reminder_id,
                status=ReminderStatus.COMPLETED,
                changed=False,
            )

        reminder.status = ReminderStatus.SNOOZED
        reminder.due_at = now + timedelta(minutes=interval_minutes)
        reminder.locked_at = None

        return ReminderResult(
            reminder_id=reminder_id,
            status=ReminderStatus.SNOOZED,
            changed=True,
        )
