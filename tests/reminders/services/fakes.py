from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nudge_bot.reminders.enums import ReminderStatus
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
