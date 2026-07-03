from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nudge_bot.reminders.domain import ReminderResult
from nudge_bot.reminders.enums import (
    CallbackActionEnum,
    CallbackEventStatusEnum,
    ReminderStatusEnum,
)
from nudge_bot.storage.models import CallbackEvent
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

        if reminder.status == ReminderStatusEnum.COMPLETED:
            return ReminderResult(
                reminder_id=reminder_id,
                status=ReminderStatusEnum.COMPLETED,
                changed=False,
                due_at=reminder.due_at,
            )

        reminder.status = ReminderStatusEnum.COMPLETED
        reminder.completed_at = now
        reminder.locked_at = None

        return ReminderResult(
            reminder_id=reminder_id,
            status=ReminderStatusEnum.COMPLETED,
            changed=True,
            due_at=reminder.due_at,
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

        if reminder.status == ReminderStatusEnum.COMPLETED:
            return ReminderResult(
                reminder_id=reminder_id,
                status=ReminderStatusEnum.COMPLETED,
                changed=False,
                due_at=reminder.due_at,
            )

        reminder.status = ReminderStatusEnum.SNOOZED
        reminder.due_at = now + timedelta(minutes=interval_minutes)
        reminder.locked_at = None

        return ReminderResult(
            reminder_id=reminder_id,
            status=ReminderStatusEnum.SNOOZED,
            changed=True,
            due_at=reminder.due_at,
        )

    async def process_callback_action(
        self,
        uow: UnitOfWork,
        *,
        callback_key: str,
        action: CallbackActionEnum,
        reminder_id: int,
        user_id: int,
        interval_minutes: int,
        now: datetime | None = None,
    ) -> ReminderResult:
        now = now or datetime.now(UTC)
        existing_event = await uow.callback_events.get_by_key(callback_key)
        if existing_event is not None:
            reminder = await uow.reminders.get_by_id_for_user(
                reminder_id=reminder_id,
                user_id=user_id,
            )
            if reminder is None:
                raise LookupError("reminder not found")

            if action == CallbackActionEnum.REPEAT and reminder.due_at <= now:
                return await self.snooze(
                    uow,
                    reminder_id=reminder_id,
                    user_id=user_id,
                    interval_minutes=interval_minutes,
                    now=now,
                )

            return ReminderResult(
                reminder_id=reminder_id,
                status=reminder.status,
                changed=False,
                due_at=reminder.due_at,
            )

        event = CallbackEvent(
            user_id=user_id,
            reminder_id=reminder_id,
            callback_key=callback_key,
            action=action,
            status=CallbackEventStatusEnum.RECEIVED,
        )
        uow.callback_events.add(event)

        try:
            if action == CallbackActionEnum.READ:
                result = await self.mark_completed(
                    uow,
                    reminder_id=reminder_id,
                    user_id=user_id,
                    now=now,
                )
            elif action == CallbackActionEnum.REPEAT:
                result = await self.snooze(
                    uow,
                    reminder_id=reminder_id,
                    user_id=user_id,
                    interval_minutes=interval_minutes,
                    now=now,
                )
            else:
                result = ReminderResult(
                    reminder_id=reminder_id,
                    status=ReminderStatusEnum.SENT,
                    changed=False,
                )
        except Exception:
            event.status = CallbackEventStatusEnum.FAILED
            raise

        event.status = CallbackEventStatusEnum.PROCESSED
        event.processed_at = now
        return result
