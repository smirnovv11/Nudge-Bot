from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.sql import Select

from nudge_bot.constants import DEFAULT_REPEAT_INTERVAL_MINUTES
from nudge_bot.reminders.enums import ReminderStatus
from nudge_bot.storage.models import Reminder
from nudge_bot.storage.repositories.reminders import ReminderRepository


class CapturingSession:
    def __init__(self, reminder: Reminder) -> None:
        self.reminder = reminder
        self.scalars_statement: object | None = None
        self.executed_statements: list[object] = []

    async def scalars(self, statement: object) -> list[int]:
        self.scalars_statement = statement
        return [self.reminder.id]

    async def execute(self, statement: object) -> list[tuple[Reminder, int, int]]:
        self.executed_statements.append(statement)
        if isinstance(statement, Select):
            return [(self.reminder, 100, 7)]
        return []


@pytest.mark.asyncio
async def test_claim_due_includes_sent_reminders_and_user_repeat_interval() -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    reminder = Reminder(
        id=1,
        user_id=10,
        status=ReminderStatus.SENT,
        reminder_text="walk the dog",
        due_at=now,
    )
    session = CapturingSession(reminder)

    result = await ReminderRepository(session).claim_due(limit=50, now=now)  # type: ignore[arg-type]

    assert result[0].repeat_interval_minutes == 7
    assert session.scalars_statement is not None
    assert "user_settings" not in str(session.scalars_statement).lower()
    assert "drafts" in str(session.scalars_statement).lower()
    assert "exists" in str(session.scalars_statement).lower()
    status_values = session.scalars_statement.compile().params["status_1"]  # type: ignore[attr-defined]
    assert status_values == [
        ReminderStatus.ACTIVE,
        ReminderStatus.SNOOZED,
        ReminderStatus.SENT,
    ]

    reminder_select = session.executed_statements[-1]
    assert "user_settings" in str(reminder_select).lower()


@pytest.mark.asyncio
async def test_claim_due_uses_default_repeat_interval_when_settings_are_missing() -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    reminder = Reminder(
        id=1,
        user_id=10,
        status=ReminderStatus.SENT,
        reminder_text="walk the dog",
        due_at=now,
    )
    session = CapturingSession(reminder)

    async def execute_without_settings(statement: object) -> list[tuple[Reminder, int, int]]:
        session.executed_statements.append(statement)
        if isinstance(statement, Select):
            return [(reminder, 100, DEFAULT_REPEAT_INTERVAL_MINUTES)]
        return []

    session.execute = execute_without_settings  # type: ignore[method-assign]

    result = await ReminderRepository(session).claim_due(limit=50, now=now)  # type: ignore[arg-type]

    assert result[0].repeat_interval_minutes == DEFAULT_REPEAT_INTERVAL_MINUTES
