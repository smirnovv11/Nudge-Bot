from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from nudge_bot.common.constants import DRAFT_EXPIRATION_HOURS
from nudge_bot.config import Settings
from nudge_bot.reminders.enums import DraftStatus, DraftType, ReminderSourceType, ReminderStatus
from nudge_bot.reminders.services import TextReminderService
from nudge_bot.reminders.services.intake import (
    SOURCE_METADATA_PAYLOAD_KEY,
    SOURCE_TYPE_PAYLOAD_KEY,
    TIMEZONE_PAYLOAD_KEY,
)
from nudge_bot.reminders.services.schemas import TextReminderOutcome

from .fakes import (
    FakeDraftRepository,
    FakeReminderRepository,
    FakeSession,
    FakeUnitOfWork,
    FakeUser,
    FakeUserRepository,
    FakeUserSettings,
)

NOW = datetime(2026, 6, 24, 12, 0, tzinfo=ZoneInfo("Europe/Minsk"))
SETTINGS = Settings()


@pytest.mark.asyncio
async def test_handle_text_reminder_creates_active_reminder_for_confident_parse() -> None:
    reminders = FakeReminderRepository()
    drafts = FakeDraftRepository()
    users = FakeUserRepository()
    session = FakeSession()
    uow = FakeUnitOfWork(reminders, drafts=drafts, users=users, session=session)

    result = await TextReminderService().handle_text_reminder(
        uow,
        telegram_user_id=100,
        username="sqd",
        locale="ru",
        text="walk the dog in 20 minutes",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == TextReminderOutcome.CREATED
    assert result.reminder is reminders.added[0]
    assert result.reminder.reminder_text == "walk the dog"
    assert result.reminder.status == ReminderStatus.ACTIVE
    assert result.reminder.source_type == ReminderSourceType.TEXT
    assert result.reminder.extra == {}
    assert result.reminder.due_at.tzinfo == UTC
    assert result.reminder.due_at.hour == 9
    assert result.reminder.due_at.minute == 20
    assert result.display_timezone == "Europe/Minsk"
    assert result.draft is None
    assert drafts.added == []
    assert users.get_or_create_called_with is not None
    assert users.get_or_create_called_with["locale"] == "ru"
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_handle_text_reminder_creates_pending_draft_for_uncertain_parse() -> None:
    reminders = FakeReminderRepository()
    drafts = FakeDraftRepository()
    uow = FakeUnitOfWork(reminders, drafts=drafts)

    result = await TextReminderService().handle_text_reminder(
        uow,
        telegram_user_id=100,
        username=None,
        locale=None,
        text="pick up order tomorrow",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == TextReminderOutcome.DRAFT
    assert result.reminder is None
    assert result.draft is drafts.added[0]
    assert result.draft.type == DraftType.REMINDER_CONFIRMATION
    assert result.draft.status == DraftStatus.PENDING
    assert result.draft.input_text == "pick up order tomorrow"
    assert result.draft.parsed_text == "pick up order"
    assert result.draft.parsed_due_at is not None
    assert result.draft.parsed_due_at.tzinfo == UTC
    assert result.draft.parse_confidence is not None
    assert result.draft.payload == {
        TIMEZONE_PAYLOAD_KEY: "Europe/Minsk",
        SOURCE_TYPE_PAYLOAD_KEY: ReminderSourceType.TEXT.value,
        SOURCE_METADATA_PAYLOAD_KEY: {},
    }
    assert result.draft.expires_at == NOW.astimezone(UTC) + timedelta(hours=DRAFT_EXPIRATION_HOURS)
    assert reminders.added == []


@pytest.mark.asyncio
async def test_handle_text_reminder_falls_back_when_user_timezone_is_invalid() -> None:
    reminders = FakeReminderRepository()
    user = FakeUser(
        id=10,
        telegram_user_id=100,
        username=None,
        locale=None,
        settings=FakeUserSettings(timezone="Invalid/Timezone"),
    )
    uow = FakeUnitOfWork(reminders, users=FakeUserRepository(user))

    result = await TextReminderService().handle_text_reminder(
        uow,
        telegram_user_id=100,
        username=None,
        locale=None,
        text="walk the dog in 20 minutes",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == TextReminderOutcome.CREATED
    assert result.display_timezone == SETTINGS.default_timezone
    assert reminders.added[0].due_at.tzinfo == UTC


@pytest.mark.asyncio
async def test_handle_text_reminder_unknown_text_creates_nothing() -> None:
    reminders = FakeReminderRepository()
    drafts = FakeDraftRepository()
    uow = FakeUnitOfWork(reminders, drafts=drafts)

    result = await TextReminderService().handle_text_reminder(
        uow,
        telegram_user_id=100,
        username=None,
        locale=None,
        text="buy milk",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == TextReminderOutcome.UNKNOWN
    assert result.reminder is None
    assert result.draft is None
    assert reminders.added == []
    assert drafts.added == []


@pytest.mark.asyncio
async def test_handle_text_reminder_note_marker_creates_nothing() -> None:
    reminders = FakeReminderRepository()
    drafts = FakeDraftRepository()
    uow = FakeUnitOfWork(reminders, drafts=drafts)

    result = await TextReminderService().handle_text_reminder(
        uow,
        telegram_user_id=100,
        username=None,
        locale=None,
        text="note: buy milk tomorrow",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == TextReminderOutcome.NOTE
    assert result.reminder is None
    assert result.draft is None
    assert reminders.added == []
    assert drafts.added == []
