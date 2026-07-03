from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nudge_bot.config import Settings
from nudge_bot.reminders.draft_payloads import (
    EDIT_TIME_CALLBACK_KEY,
    EDIT_TIME_NOTIFICATION_ID,
    EDIT_TIME_REMINDER_ID,
    edit_time_payload,
)
from nudge_bot.reminders.enums import (
    CallbackActionEnum,
    CallbackEventStatusEnum,
    DraftStatusEnum,
    DraftTypeEnum,
    ReminderStatusEnum,
)
from nudge_bot.reminders.services import ReminderEditTimeService
from nudge_bot.reminders.services.schemas import EditTimeOutcomeEnum
from nudge_bot.storage.models import Draft

from .fakes import (
    FakeCallbackEvent,
    FakeCallbackEventRepository,
    FakeDraftRepository,
    FakeReminder,
    FakeReminderRepository,
    FakeUnitOfWork,
    FakeUserRepository,
)

NOW = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_choose_time_creates_pending_edit_time_draft() -> None:
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.SENT,
        due_at=NOW,
    )
    drafts = FakeDraftRepository()
    callback_events = FakeCallbackEventRepository()
    users = FakeUserRepository()

    result = await ReminderEditTimeService().start_choose_time(
        FakeUnitOfWork(
            FakeReminderRepository(reminder),
            drafts=drafts,
            callback_events=callback_events,
            users=users,
        ),
        callback_key="reminder:1:notification:7:action:choose_time",
        reminder_id=1,
        user_id=10,
        notification_id=7,
        timezone="Europe/Minsk",
        now=NOW,
    )

    assert result.outcome == EditTimeOutcomeEnum.AWAITING_INPUT
    assert result.changed is True
    assert len(drafts.added) == 1
    draft = drafts.added[0]
    assert draft.type == DraftTypeEnum.REMINDER_EDIT_TIME
    assert draft.status == DraftStatusEnum.PENDING
    assert draft.payload[EDIT_TIME_REMINDER_ID] == 1
    assert draft.payload[EDIT_TIME_NOTIFICATION_ID] == 7
    assert draft.payload[EDIT_TIME_CALLBACK_KEY] == "reminder:1:notification:7:action:choose_time"
    assert callback_events.added[0].status == CallbackEventStatusEnum.PROCESSED
    assert users.locked_lookup_called is True


@pytest.mark.asyncio
async def test_repeated_choose_time_reuses_pending_draft() -> None:
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.SENT,
        due_at=NOW,
    )
    draft = _edit_time_draft(reminder_id=1)
    event = FakeCallbackEvent(
        user_id=10,
        reminder_id=1,
        callback_key="reminder:1:notification:7:action:choose_time",
        action=CallbackActionEnum.CHOOSE_TIME,
        status=CallbackEventStatusEnum.PROCESSED,
    )
    drafts = FakeDraftRepository(draft)
    callback_events = FakeCallbackEventRepository(event)

    result = await ReminderEditTimeService().start_choose_time(
        FakeUnitOfWork(
            FakeReminderRepository(reminder),
            drafts=drafts,
            callback_events=callback_events,
        ),
        callback_key="reminder:1:notification:7:action:choose_time",
        reminder_id=1,
        user_id=10,
        notification_id=7,
        timezone="Europe/Minsk",
        now=NOW,
    )

    assert result.outcome == EditTimeOutcomeEnum.AWAITING_INPUT
    assert result.changed is False
    assert drafts.added == []


@pytest.mark.asyncio
async def test_choose_time_replaces_pending_draft_for_other_reminder() -> None:
    reminder = FakeReminder(
        id=2,
        user_id=10,
        status=ReminderStatusEnum.SENT,
        due_at=NOW,
    )
    previous_draft = _edit_time_draft(reminder_id=1)
    drafts = FakeDraftRepository(previous_draft)

    result = await ReminderEditTimeService().start_choose_time(
        FakeUnitOfWork(
            FakeReminderRepository(reminder),
            drafts=drafts,
        ),
        callback_key="reminder:2:notification:8:action:choose_time",
        reminder_id=2,
        user_id=10,
        notification_id=8,
        timezone="Europe/Minsk",
        now=NOW,
    )

    assert result.outcome == EditTimeOutcomeEnum.AWAITING_INPUT
    assert result.changed is True
    assert previous_draft.status == DraftStatusEnum.CANCELLED
    assert len(drafts.added) == 1
    assert drafts.added[0].payload[EDIT_TIME_REMINDER_ID] == 2


@pytest.mark.asyncio
async def test_choose_time_does_not_change_completed_reminder() -> None:
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.COMPLETED,
        due_at=NOW,
        completed_at=NOW,
    )
    drafts = FakeDraftRepository()
    reminders = FakeReminderRepository(reminder)

    result = await ReminderEditTimeService().start_choose_time(
        FakeUnitOfWork(reminders, drafts=drafts),
        callback_key="reminder:1:notification:7:action:choose_time",
        reminder_id=1,
        user_id=10,
        notification_id=7,
        timezone="Europe/Minsk",
        now=NOW,
    )

    assert result.outcome == EditTimeOutcomeEnum.ALREADY_HANDLED
    assert result.changed is False
    assert drafts.added == []
    assert reminder.status == ReminderStatusEnum.COMPLETED
    assert reminders.locked_lookup_called is True


@pytest.mark.asyncio
async def test_edit_time_text_reschedules_reminder_and_confirms_draft() -> None:
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.SENT,
        due_at=NOW,
        locked_at=NOW,
    )
    draft = _edit_time_draft(reminder_id=1)

    result = await ReminderEditTimeService().apply_edit_time_text(
        FakeUnitOfWork(FakeReminderRepository(reminder), drafts=FakeDraftRepository(draft)),
        telegram_user_id=100,
        username=None,
        locale="ru",
        text="через 20 минут",
        now=NOW,
        settings=Settings(),
    )

    assert result.outcome == EditTimeOutcomeEnum.RESCHEDULED
    assert result.changed is True
    assert reminder.status == ReminderStatusEnum.SNOOZED
    assert reminder.due_at == NOW + timedelta(minutes=20)
    assert reminder.locked_at is None
    assert draft.status == DraftStatusEnum.CONFIRMED
    assert draft.parsed_due_at == reminder.due_at


@pytest.mark.asyncio
async def test_edit_time_text_does_not_resurrect_completed_reminder() -> None:
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.COMPLETED,
        due_at=NOW,
        completed_at=NOW,
    )
    draft = _edit_time_draft(reminder_id=1)
    reminders = FakeReminderRepository(reminder)

    result = await ReminderEditTimeService().apply_edit_time_text(
        FakeUnitOfWork(reminders, drafts=FakeDraftRepository(draft)),
        telegram_user_id=100,
        username=None,
        locale="ru",
        text="через 20 минут",
        now=NOW,
        settings=Settings(),
    )

    assert result.outcome == EditTimeOutcomeEnum.ALREADY_HANDLED
    assert result.changed is True
    assert reminder.status == ReminderStatusEnum.COMPLETED
    assert reminder.due_at == NOW
    assert draft.status == DraftStatusEnum.CANCELLED
    assert reminders.locked_lookup_called is True


@pytest.mark.asyncio
async def test_edit_time_text_does_not_clobber_sending_reminder() -> None:
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.SENDING,
        due_at=NOW,
        locked_at=NOW,
    )
    draft = _edit_time_draft(reminder_id=1)

    result = await ReminderEditTimeService().apply_edit_time_text(
        FakeUnitOfWork(FakeReminderRepository(reminder), drafts=FakeDraftRepository(draft)),
        telegram_user_id=100,
        username=None,
        locale="ru",
        text="через 20 минут",
        now=NOW,
        settings=Settings(),
    )

    assert result.outcome == EditTimeOutcomeEnum.ALREADY_HANDLED
    assert reminder.status == ReminderStatusEnum.SENDING
    assert reminder.locked_at == NOW
    assert draft.status == DraftStatusEnum.CANCELLED


@pytest.mark.asyncio
async def test_unknown_edit_time_text_keeps_draft_pending() -> None:
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.SENT,
        due_at=NOW,
    )
    draft = _edit_time_draft(reminder_id=1)

    result = await ReminderEditTimeService().apply_edit_time_text(
        FakeUnitOfWork(
            FakeReminderRepository(reminder),
            drafts=FakeDraftRepository(draft),
        ),
        telegram_user_id=100,
        username=None,
        locale="ru",
        text="когда-нибудь потом",
        now=NOW,
        settings=Settings(),
    )

    assert result.outcome == EditTimeOutcomeEnum.UNKNOWN
    assert reminder.due_at == NOW
    assert draft.status == DraftStatusEnum.PENDING
    assert draft.input_text == "когда-нибудь потом"


@pytest.mark.asyncio
async def test_expired_edit_time_draft_does_not_change_reminder() -> None:
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.SENT,
        due_at=NOW,
    )
    draft = _edit_time_draft(reminder_id=1, expires_at=NOW - timedelta(seconds=1))

    result = await ReminderEditTimeService().apply_edit_time_text(
        FakeUnitOfWork(
            FakeReminderRepository(reminder),
            drafts=FakeDraftRepository(draft),
        ),
        telegram_user_id=100,
        username=None,
        locale="ru",
        text="через 20 минут",
        now=NOW,
        settings=Settings(),
    )

    assert result.outcome == EditTimeOutcomeEnum.EXPIRED
    assert reminder.due_at == NOW
    assert draft.status == DraftStatusEnum.EXPIRED


def _edit_time_draft(
    *,
    reminder_id: int,
    expires_at: datetime | None = None,
) -> Draft:
    return Draft(
        id=1,
        user_id=10,
        type=DraftTypeEnum.REMINDER_EDIT_TIME,
        status=DraftStatusEnum.PENDING,
        input_text="",
        parsed_text=None,
        parsed_due_at=None,
        parse_confidence=None,
        payload=edit_time_payload(
            reminder_id=reminder_id,
            notification_id=7,
            callback_key="reminder:1:notification:7:action:choose_time",
            timezone="Europe/Minsk",
        ),
        expires_at=expires_at or NOW + timedelta(hours=12),
    )
