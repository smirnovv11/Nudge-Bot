from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nudge_bot.reminders.enums import CallbackEventStatus, ReminderDeliveryStatus, ReminderStatus
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
class FakeReminderAttempt:
    id: int
    reminder_id: int
    attempt_no: int
    scheduled_for: datetime
    delivery_status: ReminderDeliveryStatus
    sent_at: datetime | None = None
    telegram_message_id: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    next_retry_at: datetime | None = None


@dataclass
class FakeCallbackEvent:
    user_id: int
    reminder_id: int | None
    callback_key: str
    action: object
    status: CallbackEventStatus
    processed_at: datetime | None = None


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
        self.mark_delivery_sent_called_with: dict[str, object] | None = None
        self.mark_delivery_failed_called_with: dict[str, object] | None = None

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

    async def mark_delivery_sent(self, *, reminder_id: int, now: datetime) -> None:
        self.mark_delivery_sent_called_with = {"reminder_id": reminder_id, "now": now}
        if self.reminder is not None and self.reminder.id == reminder_id:
            self.reminder.status = ReminderStatus.SENT
            self.reminder.locked_at = None

    async def mark_delivery_failed(self, *, reminder_id: int) -> None:
        self.mark_delivery_failed_called_with = {"reminder_id": reminder_id}
        if self.reminder is not None and self.reminder.id == reminder_id:
            self.reminder.status = ReminderStatus.ACTIVE
            self.reminder.locked_at = None


class FakeReminderAttemptRepository:
    def __init__(self) -> None:
        self.attempts: list[FakeReminderAttempt] = []

    async def create_sending(
        self,
        *,
        reminder_id: int,
        scheduled_for: datetime,
    ) -> FakeReminderAttempt:
        attempt = FakeReminderAttempt(
            id=len(self.attempts) + 1,
            reminder_id=reminder_id,
            attempt_no=len(self.attempts) + 1,
            scheduled_for=scheduled_for,
            delivery_status=ReminderDeliveryStatus.SENDING,
        )
        self.attempts.append(attempt)
        return attempt

    async def mark_sent(
        self,
        *,
        attempt_id: int,
        telegram_message_id: int,
        sent_at: datetime,
    ) -> None:
        attempt = self.attempts[attempt_id - 1]
        attempt.delivery_status = ReminderDeliveryStatus.SENT
        attempt.telegram_message_id = telegram_message_id
        attempt.sent_at = sent_at

    async def mark_failed(
        self,
        *,
        attempt_id: int,
        error_code: str,
        error_message: str,
    ) -> None:
        attempt = self.attempts[attempt_id - 1]
        attempt.delivery_status = ReminderDeliveryStatus.FAILED
        attempt.error_code = error_code
        attempt.error_message = error_message


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

    async def get_by_telegram_id(self, telegram_user_id: int) -> FakeUser | None:
        if self.user.telegram_user_id == telegram_user_id:
            return self.user
        return None


class FakeCallbackEventRepository:
    def __init__(self, event: FakeCallbackEvent | None = None) -> None:
        self.event = event
        self.added: list[object] = []

    async def get_by_key(self, callback_key: str) -> object | None:
        if self.event is not None and self.event.callback_key == callback_key:
            return self.event
        return None

    def add(self, event: object) -> None:
        self.added.append(event)


class FakeUnitOfWork:
    def __init__(
        self,
        reminders: FakeReminderRepository | None = None,
        *,
        drafts: FakeDraftRepository | None = None,
        users: FakeUserRepository | None = None,
        attempts: FakeReminderAttemptRepository | None = None,
        callback_events: FakeCallbackEventRepository | None = None,
        session: FakeSession | None = None,
    ) -> None:
        self.users = users or FakeUserRepository()
        self.reminders = reminders
        self.drafts = drafts or FakeDraftRepository()
        self.attempts = attempts or FakeReminderAttemptRepository()
        self.callback_events = callback_events or FakeCallbackEventRepository()
        self.session = session or FakeSession()
