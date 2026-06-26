from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from nudge_bot.common.constants import DRAFT_EXPIRATION_HOURS
from nudge_bot.config import Settings
from nudge_bot.reminders.enums import DraftStatus, DraftType, ReminderStatus
from nudge_bot.reminders.service import (
    cancel_draft,
    claim_due_reminders,
    confirm_draft,
    handle_text_reminder,
    mark_completed,
    snooze,
)
from nudge_bot.storage.models import Draft


@dataclass
class FakeReminder:
    id: int
    user_id: int
    status: ReminderStatus
    due_at: datetime
    completed_at: datetime | None = None
    locked_at: datetime | None = None


@dataclass
class FakeUserSettings:
    timezone: str = "Europe/Minsk"
    repeat_interval_minutes: int = 5


@dataclass
class FakeUser:
    id: int
    telegram_user_id: int
    username: str | None
    locale: str | None
    settings: FakeUserSettings


class FakeSession:
    def __init__(self) -> None:
        self.flush_count = 0

    async def flush(self) -> None:
        self.flush_count += 1


class FakeReminderRepository:
    def __init__(self, reminder: FakeReminder | None = None) -> None:
        self.reminder = reminder
        self.added: list[object] = []
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

    def add(self, reminder: object) -> None:
        self.added.append(reminder)


class FakeDraftRepository:
    def __init__(self, draft: Draft | None = None) -> None:
        self.draft = draft
        self.added: list[Draft] = []
        self.locked_lookup_called = False

    async def get_by_id_for_user(self, *, draft_id: int, user_id: int) -> Draft | None:
        if self.draft is None:
            return None
        if self.draft.id == draft_id and self.draft.user_id == user_id:
            return self.draft
        return None

    async def get_by_id_for_user_for_update(self, *, draft_id: int, user_id: int) -> Draft | None:
        self.locked_lookup_called = True
        return await self.get_by_id_for_user(draft_id=draft_id, user_id=user_id)

    def add(self, draft: Draft) -> None:
        draft.id = len(self.added) + 1
        self.added.append(draft)


class FakeUserRepository:
    def __init__(self, user: FakeUser | None = None) -> None:
        self.user = user or FakeUser(
            id=10,
            telegram_user_id=100,
            username=None,
            locale=None,
            settings=FakeUserSettings(),
        )
        self.get_or_create_called_with: dict[str, object] | None = None

    async def get_or_create(
        self,
        *,
        telegram_user_id: int,
        username: str | None,
        locale: str | None,
        timezone: str,
        repeat_interval_minutes: int,
    ) -> FakeUser:
        self.get_or_create_called_with = {
            "telegram_user_id": telegram_user_id,
            "username": username,
            "locale": locale,
            "timezone": timezone,
            "repeat_interval_minutes": repeat_interval_minutes,
        }
        self.user.telegram_user_id = telegram_user_id
        self.user.username = username
        self.user.locale = locale
        return self.user


class FakeUnitOfWork:
    def __init__(
        self,
        reminders: FakeReminderRepository | None = None,
        *,
        drafts: FakeDraftRepository | None = None,
        users: FakeUserRepository | None = None,
        session: FakeSession | None = None,
    ) -> None:
        self.users = users or FakeUserRepository()
        self.reminders = reminders
        self.drafts = drafts or FakeDraftRepository()
        self.session = session or FakeSession()


NOW = datetime(2026, 6, 24, 12, 0, tzinfo=ZoneInfo("Europe/Minsk"))
SETTINGS = Settings()


@pytest.mark.asyncio
async def test_claim_due_reminders_delegates_to_repository() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    repository = FakeReminderRepository()
    uow = FakeUnitOfWork(repository)

    result = await claim_due_reminders(uow, limit=50, now=now)

    assert result == []
    assert repository.claim_due_called_with == (50, now)


@pytest.mark.asyncio
async def test_handle_text_reminder_creates_active_reminder_for_confident_parse() -> None:
    reminders = FakeReminderRepository()
    drafts = FakeDraftRepository()
    users = FakeUserRepository()
    session = FakeSession()
    uow = FakeUnitOfWork(reminders, drafts=drafts, users=users, session=session)

    result = await handle_text_reminder(
        uow,
        telegram_user_id=100,
        username="sqd",
        locale="ru",
        text="walk the dog in 20 minutes",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == "created"
    assert result.reminder is reminders.added[0]
    assert result.reminder.reminder_text == "walk the dog"
    assert result.reminder.status == ReminderStatus.ACTIVE
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

    result = await handle_text_reminder(
        uow,
        telegram_user_id=100,
        username=None,
        locale=None,
        text="pick up order tomorrow",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == "draft"
    assert result.reminder is None
    assert result.draft is drafts.added[0]
    assert result.draft.type == DraftType.REMINDER_CONFIRMATION
    assert result.draft.status == DraftStatus.PENDING
    assert result.draft.input_text == "pick up order tomorrow"
    assert result.draft.parsed_text == "pick up order"
    assert result.draft.parsed_due_at is not None
    assert result.draft.parsed_due_at.tzinfo == UTC
    assert result.draft.parse_confidence is not None
    assert result.draft.payload == {"timezone": "Europe/Minsk"}
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

    result = await handle_text_reminder(
        uow,
        telegram_user_id=100,
        username=None,
        locale=None,
        text="walk the dog in 20 minutes",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == "created"
    assert result.display_timezone == SETTINGS.default_timezone
    assert reminders.added[0].due_at.tzinfo == UTC


@pytest.mark.asyncio
async def test_handle_text_reminder_unknown_text_creates_nothing() -> None:
    reminders = FakeReminderRepository()
    drafts = FakeDraftRepository()
    uow = FakeUnitOfWork(reminders, drafts=drafts)

    result = await handle_text_reminder(
        uow,
        telegram_user_id=100,
        username=None,
        locale=None,
        text="buy milk",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == "unknown"
    assert result.reminder is None
    assert result.draft is None
    assert reminders.added == []
    assert drafts.added == []


@pytest.mark.asyncio
async def test_handle_text_reminder_note_marker_creates_nothing() -> None:
    reminders = FakeReminderRepository()
    drafts = FakeDraftRepository()
    uow = FakeUnitOfWork(reminders, drafts=drafts)

    result = await handle_text_reminder(
        uow,
        telegram_user_id=100,
        username=None,
        locale=None,
        text="note: buy milk tomorrow",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == "note"
    assert result.reminder is None
    assert result.draft is None
    assert reminders.added == []
    assert drafts.added == []


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

    first = await confirm_draft(uow, draft_id=1, user_id=10, now=NOW)
    second = await confirm_draft(uow, draft_id=1, user_id=10, now=NOW)

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

    result = await confirm_draft(uow, draft_id=1, user_id=10, now=NOW)

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

    first = await cancel_draft(uow, draft_id=1, user_id=10, now=NOW)
    second = await cancel_draft(uow, draft_id=1, user_id=10, now=NOW)

    assert first.outcome == "cancelled"
    assert first.changed is True
    assert draft.status == DraftStatus.CANCELLED
    assert second.outcome == "already_cancelled"
    assert second.changed is False
    assert reminders.added == []
    assert drafts.locked_lookup_called is True


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
