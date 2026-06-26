from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from nudge_bot.reminders.enums import DraftStatus, DraftType
from nudge_bot.reminders.services import DraftFlowService
from nudge_bot.storage.models import Draft

from .fakes import FakeDraftRepository, FakeReminderRepository, FakeUnitOfWork

NOW = datetime(2026, 6, 24, 12, 0, tzinfo=ZoneInfo("Europe/Minsk"))


@pytest.mark.asyncio
async def test_confirm_draft_creates_reminder_once_and_marks_confirmed() -> None:
    draft = Draft(
        id=1,
        user_id=10,
        type=DraftType.REMINDER_CONFIRMATION,
        status=DraftStatus.PENDING,
        input_text="pick up order tomorrow",
        parsed_text="pick up order",
        parsed_due_at=NOW + timedelta(days=1),
        parse_confidence=0.6,
        payload={},
        expires_at=NOW + timedelta(hours=24),
    )
    reminders = FakeReminderRepository()
    drafts = FakeDraftRepository(draft)
    uow = FakeUnitOfWork(reminders, drafts=drafts)
    service = DraftFlowService()

    first = await service.confirm_draft(uow, draft_id=1, user_id=10, now=NOW)
    second = await service.confirm_draft(uow, draft_id=1, user_id=10, now=NOW)

    assert first.outcome == "confirmed"
    assert first.changed is True
    assert first.reminder is reminders.added[0]
    assert first.reminder.reminder_text == "pick up order"
    assert draft.status == DraftStatus.CONFIRMED
    assert second.outcome == "already_confirmed"
    assert second.changed is False
    assert len(reminders.added) == 1
    assert drafts.locked_lookup_called is True


@pytest.mark.asyncio
async def test_confirm_draft_marks_expired_draft_without_creating_reminder() -> None:
    draft = Draft(
        id=1,
        user_id=10,
        type=DraftType.REMINDER_CONFIRMATION,
        status=DraftStatus.PENDING,
        input_text="pick up order tomorrow",
        parsed_text="pick up order",
        parsed_due_at=NOW + timedelta(days=1),
        parse_confidence=0.6,
        payload={"timezone": "Europe/Minsk"},
        expires_at=NOW.astimezone(UTC) - timedelta(seconds=1),
    )
    reminders = FakeReminderRepository()
    uow = FakeUnitOfWork(reminders, drafts=FakeDraftRepository(draft))

    result = await DraftFlowService().confirm_draft(uow, draft_id=1, user_id=10, now=NOW)

    assert result.outcome == "expired"
    assert result.changed is True
    assert result.display_timezone == "Europe/Minsk"
    assert draft.status == DraftStatus.EXPIRED
    assert reminders.added == []


@pytest.mark.asyncio
async def test_cancel_draft_marks_cancelled_once() -> None:
    draft = Draft(
        id=1,
        user_id=10,
        type=DraftType.REMINDER_CONFIRMATION,
        status=DraftStatus.PENDING,
        input_text="pick up order tomorrow",
        parsed_text="pick up order",
        parsed_due_at=NOW + timedelta(days=1),
        parse_confidence=0.6,
        payload={},
        expires_at=NOW + timedelta(hours=24),
    )
    reminders = FakeReminderRepository()
    drafts = FakeDraftRepository(draft)
    uow = FakeUnitOfWork(reminders, drafts=drafts)
    service = DraftFlowService()

    first = await service.cancel_draft(uow, draft_id=1, user_id=10, now=NOW)
    second = await service.cancel_draft(uow, draft_id=1, user_id=10, now=NOW)

    assert first.outcome == "cancelled"
    assert first.changed is True
    assert draft.status == DraftStatus.CANCELLED
    assert second.outcome == "already_cancelled"
    assert second.changed is False
    assert reminders.added == []
    assert drafts.locked_lookup_called is True
