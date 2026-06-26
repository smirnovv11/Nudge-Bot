from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from nudge_bot.reminders.domain import ReminderToSend
from nudge_bot.reminders.enums import ReminderStatus
from nudge_bot.storage.models import Reminder, User


class ReminderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_due(self, *, limit: int, now: datetime) -> list[ReminderToSend]:
        due_query = (
            select(Reminder.id)
            .where(
                Reminder.archived_at.is_(None),
                Reminder.status.in_([ReminderStatus.ACTIVE, ReminderStatus.SNOOZED]),
                Reminder.due_at <= now,
            )
            .order_by(Reminder.due_at, Reminder.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        reminder_ids = list(await self._session.scalars(due_query))

        if not reminder_ids:
            return []

        await self._session.execute(
            update(Reminder)
            .where(Reminder.id.in_(reminder_ids))
            .values(status=ReminderStatus.SENDING, locked_at=now)
        )

        reminders_query = (
            select(Reminder, User.telegram_user_id)
            .join(User, User.id == Reminder.user_id)
            .where(Reminder.id.in_(reminder_ids))
            .order_by(Reminder.due_at, Reminder.id)
        )
        rows = await self._session.execute(reminders_query)

        return [
            ReminderToSend(
                reminder_id=reminder.id,
                user_id=reminder.user_id,
                telegram_user_id=telegram_user_id,
                reminder_text=reminder.reminder_text,
                due_at=reminder.due_at,
            )
            for reminder, telegram_user_id in rows
        ]

    async def get_by_id_for_user(self, *, reminder_id: int, user_id: int) -> Reminder | None:
        return await self._session.scalar(
            select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
        )

    async def get_by_id(self, reminder_id: int) -> Reminder | None:
        return await self._session.get(Reminder, reminder_id)

    async def mark_delivery_sent(
        self,
        *,
        reminder_id: int,
        now: datetime,
    ) -> None:
        await self._session.execute(
            update(Reminder)
            .where(Reminder.id == reminder_id)
            .values(status=ReminderStatus.SENT, locked_at=None)
        )

    async def mark_delivery_failed(
        self,
        *,
        reminder_id: int,
    ) -> None:
        await self._session.execute(
            update(Reminder)
            .where(Reminder.id == reminder_id)
            .values(status=ReminderStatus.ACTIVE, locked_at=None)
        )

    def add(self, reminder: Reminder) -> None:
        self._session.add(reminder)
