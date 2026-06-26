from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nudge_bot.reminders.services import ReminderSchedulerService

from .fakes import FakeReminderRepository, FakeUnitOfWork


@pytest.mark.asyncio
async def test_claim_due_reminders_delegates_to_repository() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    repository = FakeReminderRepository()
    uow = FakeUnitOfWork(repository)

    result = await ReminderSchedulerService().claim_due_reminders(uow, limit=50, now=now)

    assert result == []
    assert repository.claim_due_called_with == (50, now)
