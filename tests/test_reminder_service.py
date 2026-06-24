from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from nudge_bot.reminders.enums import ReminderStatus
from nudge_bot.reminders.service import claim_due_reminders, mark_completed, snooze


@dataclass
class FakeReminder:
    id: int
    user_id: int
    status: ReminderStatus
    due_at: datetime
    completed_at: datetime | None = None
    locked_at: datetime | None = None


class FakeReminderRepository:
    def __init__(self, reminder: FakeReminder | None = None) -> None:
        self.reminder = reminder
        self.claim_due_called_with: tuple[int, datetime] | None = None

    async def claim_due(self, *, limit: int, now: datetime) -> list[object]:
        self.claim_due_called_with = (limit, now)
        return []

    async def get_by_id_for_user(self, *, reminder_id: int, user_id: int) -> FakeReminder | None:
        if self.reminder is None:
            return None
        if self.reminder.id == reminder_id and self.reminder.user_id == user_id:
            return self.reminder
        return None


class FakeUnitOfWork:
    def __init__(self, reminders: FakeReminderRepository) -> None:
        self.reminders = reminders


@pytest.mark.asyncio
async def test_claim_due_reminders_delegates_to_repository() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    repository = FakeReminderRepository()
    uow = FakeUnitOfWork(repository)

    result = await claim_due_reminders(uow, limit=50, now=now)

    assert result == []
    assert repository.claim_due_called_with == (50, now)


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

    result = await mark_completed(
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

    result = await snooze(
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
