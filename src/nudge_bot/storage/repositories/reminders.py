from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from nudge_bot.constants import DEFAULT_REPEAT_INTERVAL_MINUTES
from nudge_bot.reminders.domain import ReminderToSend
from nudge_bot.reminders.draft_payloads import EDIT_TIME_REMINDER_ID
from nudge_bot.reminders.enums import (
    DraftStatusEnum,
    DraftTypeEnum,
    ReminderDeliveryStatusEnum,
    ReminderStatusEnum,
)
from nudge_bot.storage.models import Draft, Reminder, ReminderAttempt, User, UserSettings

DELIVERABLE_STATUSES = [
    ReminderStatusEnum.ACTIVE,
    ReminderStatusEnum.SNOOZED,
    ReminderStatusEnum.SENT,
]


class ReminderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_due(self, *, limit: int, now: datetime) -> list[ReminderToSend]:
        due_query = (
            select(Reminder.id, Reminder.status)
            .where(
                Reminder.archived_at.is_(None),
                Reminder.status.in_(DELIVERABLE_STATUSES),
                Reminder.due_at <= now,
                ~select(Draft.id)
                .where(
                    Draft.user_id == Reminder.user_id,
                    Draft.type == DraftTypeEnum.REMINDER_EDIT_TIME,
                    Draft.status == DraftStatusEnum.PENDING,
                    Draft.expires_at > now,
                    Draft.payload[EDIT_TIME_REMINDER_ID].as_integer() == Reminder.id,
                )
                .exists(),
            )
            .order_by(Reminder.due_at, Reminder.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        due_rows = list(await self._session.execute(due_query))
        reminder_statuses = {reminder_id: status for reminder_id, status in due_rows}
        reminder_ids = list(reminder_statuses)

        if not reminder_ids:
            return []

        previous_message_id = (
            select(ReminderAttempt.telegram_message_id)
            .where(
                ReminderAttempt.reminder_id == Reminder.id,
                ReminderAttempt.delivery_status == ReminderDeliveryStatusEnum.SENT,
                ReminderAttempt.telegram_message_id.is_not(None),
            )
            .order_by(ReminderAttempt.attempt_no.desc())
            .limit(1)
            .scalar_subquery()
        )

        await self._session.execute(
            update(Reminder)
            .where(Reminder.id.in_(reminder_ids))
            .values(status=ReminderStatusEnum.SENDING, locked_at=now)
        )

        reminders_query = (
            select(
                Reminder,
                User.telegram_user_id,
                func.coalesce(
                    UserSettings.repeat_interval_minutes,
                    DEFAULT_REPEAT_INTERVAL_MINUTES,
                ),
                previous_message_id,
            )
            .join(User, User.id == Reminder.user_id)
            .outerjoin(UserSettings, UserSettings.user_id == User.id)
            .where(Reminder.id.in_(reminder_ids))
            .order_by(Reminder.due_at, Reminder.id)
        )
        rows = await self._session.execute(reminders_query)

        reminders_to_send = []
        for (
            reminder,
            telegram_user_id,
            repeat_interval_minutes,
            last_telegram_message_id,
        ) in rows:
            reminders_to_send.append(
                ReminderToSend(
                    reminder_id=reminder.id,
                    user_id=reminder.user_id,
                    telegram_user_id=telegram_user_id,
                    reminder_text=reminder.reminder_text,
                    due_at=reminder.due_at,
                    repeat_interval_minutes=repeat_interval_minutes,
                    is_auto_repeat=reminder_statuses[reminder.id] == ReminderStatusEnum.SENT,
                    previous_telegram_message_id=last_telegram_message_id,
                )
            )

        return reminders_to_send

    async def get_by_id_for_user(self, *, reminder_id: int, user_id: int) -> Reminder | None:
        return await self._session.scalar(
            select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
        )

    async def get_by_id_for_user_for_update(
        self,
        *,
        reminder_id: int,
        user_id: int,
    ) -> Reminder | None:
        return await self._session.scalar(
            select(Reminder)
            .where(Reminder.id == reminder_id, Reminder.user_id == user_id)
            .with_for_update()
        )

    async def get_by_id(self, reminder_id: int) -> Reminder | None:
        return await self._session.get(Reminder, reminder_id)

    async def mark_delivery_sent(
        self,
        *,
        reminder_id: int,
        now: datetime,
        repeat_interval_minutes: int,
    ) -> None:
        await self._session.execute(
            update(Reminder)
            .where(Reminder.id == reminder_id, Reminder.status == ReminderStatusEnum.SENDING)
            .values(
                status=ReminderStatusEnum.SENT,
                due_at=now + timedelta(minutes=repeat_interval_minutes),
                locked_at=None,
            )
        )

    async def mark_delivery_failed(
        self,
        *,
        reminder_id: int,
    ) -> None:
        await self._session.execute(
            update(Reminder)
            .where(Reminder.id == reminder_id, Reminder.status == ReminderStatusEnum.SENDING)
            .values(status=ReminderStatusEnum.ACTIVE, locked_at=None)
        )

    def add(self, reminder: Reminder) -> None:
        self._session.add(reminder)
