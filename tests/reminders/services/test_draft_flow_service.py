from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from nudge_bot.reminders.enums import DraftStatus, DraftType, ReminderSourceType
from nudge_bot.reminders.services import DraftFlowService
from nudge_bot.reminders.services.intake import SOURCE_METADATA_PAYLOAD_KEY, SOURCE_TYPE_PAYLOAD_KEY
from nudge_bot.reminders.services.schemas import DraftActionOutcome
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

    assert first.outcome == DraftActionOutcome.CONFIRMED
    assert first.changed is True
    assert first.reminder is reminders.added[0]
    assert first.reminder.reminder_text == "pick up order"
    assert draft.status == DraftStatus.CONFIRMED
    assert second.outcome == DraftActionOutcome.ALREADY_CONFIRMED
    assert second.changed is False
    assert len(reminders.added) == 1
    assert drafts.locked_lookup_called is True


@pytest.mark.asyncio
async def test_confirm_voice_draft_preserves_source_metadata() -> None:
    source_metadata = {
        "language": "ru",
        "model": "small",
        "source_file_unique_id": "voice-file",
    }
    draft = Draft(
        id=1,
        user_id=10,
        type=DraftType.REMINDER_CONFIRMATION,
        status=DraftStatus.PENDING,
        input_text="walk the dog in 20 minutes",
        parsed_text="walk the dog",
        parsed_due_at=NOW + timedelta(minutes=20),
        parse_confidence=0.6,
        payload={
            SOURCE_TYPE_PAYLOAD_KEY: ReminderSourceType.VOICE.value,
            SOURCE_METADATA_PAYLOAD_KEY: source_metadata,
        },
        expires_at=NOW + timedelta(hours=24),
    )
    reminders = FakeReminderRepository()
    uow = FakeUnitOfWork(reminders, drafts=FakeDraftRepository(draft))

    result = await DraftFlowService().confirm_draft(uow, draft_id=1, user_id=10, now=NOW)

    assert result.outcome == DraftActionOutcome.CONFIRMED
    assert result.reminder is reminders.added[0]
    assert result.reminder.source_type == ReminderSourceType.VOICE
    assert result.reminder.extra == source_metadata


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

    assert result.outcome == DraftActionOutcome.EXPIRED
    assert result.changed is True
    assert result.display_timezone == "Europe/Minsk"
    assert draft.status == DraftStatus.EXPIRED
    assert reminders.added == []


@pytest.mark.asyncio
async def test_confirm_draft_marks_past_due_candidate_expired() -> None:
    draft = Draft(
        id=1,
        user_id=10,
        type=DraftType.REMINDER_CONFIRMATION,
        status=DraftStatus.PENDING,
        input_text="pick up order tomorrow",
        parsed_text="pick up order",
        parsed_due_at=NOW.astimezone(UTC) - timedelta(seconds=1),
        parse_confidence=0.6,
        payload={"timezone": "Europe/Minsk"},
        expires_at=NOW.astimezone(UTC) + timedelta(hours=1),
    )
    reminders = FakeReminderRepository()
    uow = FakeUnitOfWork(reminders, drafts=FakeDraftRepository(draft))

    result = await DraftFlowService().confirm_draft(uow, draft_id=1, user_id=10, now=NOW)

    assert result.outcome == DraftActionOutcome.EXPIRED
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

    assert first.outcome == DraftActionOutcome.CANCELLED
    assert first.changed is True
    assert draft.status == DraftStatus.CANCELLED
    assert second.outcome == DraftActionOutcome.ALREADY_CANCELLED
    assert second.changed is False
    assert reminders.added == []
    assert drafts.locked_lookup_called is True
