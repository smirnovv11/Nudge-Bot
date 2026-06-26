from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nudge_bot.reminders.enums import ReminderStatus
from nudge_bot.reminders.services import ReminderActionService

from .fakes import FakeReminder, FakeReminderRepository, FakeUnitOfWork


@pytest.mark.asyncio
async def test_mark_completed_is_idempotent_for_completed_reminder() -> None:
    completed_at = datetime(2026, 6, 24, 11, 0, tzinfo=UTC)
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatus.COMPLETED,
        due_at=completed_at,
        completed_at=completed_at,
    )

    result = await ReminderActionService().mark_completed(
        FakeUnitOfWork(FakeReminderRepository(reminder)),
        reminder_id=1,
        user_id=10,
        now=datetime(2026, 6, 24, 12, 0, tzinfo=UTC),
    )

    assert result.status == ReminderStatus.COMPLETED
    assert result.changed is False
    assert reminder.completed_at == completed_at


@pytest.mark.asyncio
async def test_snooze_updates_due_time_for_active_reminder() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatus.ACTIVE,
        due_at=now,
        locked_at=now,
    )

    result = await ReminderActionService().snooze(
        FakeUnitOfWork(FakeReminderRepository(reminder)),
        reminder_id=1,
        user_id=10,
        interval_minutes=5,
        now=now,
    )

    assert result.status == ReminderStatus.SNOOZED
    assert result.changed is True
    assert reminder.status == ReminderStatus.SNOOZED
    assert reminder.due_at == now + timedelta(minutes=5)
    assert reminder.locked_at is None
