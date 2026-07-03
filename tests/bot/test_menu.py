from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from nudge_bot.bot.callbacks import MenuActionEnum, MenuCallback
from nudge_bot.bot.keyboards import (
    MENU_ACTIVE_BUTTON_TEXT,
    MENU_ARCHIVE_BUTTON_TEXT,
    MENU_HELP_BUTTON_TEXT,
    MENU_HISTORY_BUTTON_TEXT,
    MENU_NEW_REMINDER_BUTTON_TEXT,
    MENU_SETTINGS_BUTTON_TEXT,
    REPEAT_INTERVAL_PRESETS,
    TIMEZONE_PRESETS,
    bottom_menu_keyboard,
    main_menu_keyboard,
    repeat_interval_menu_keyboard,
    timezone_menu_keyboard,
)
from nudge_bot.bot.routers import menu
from nudge_bot.config import Settings
from nudge_bot.reminders.enums import ReminderStatusEnum
from nudge_bot.storage.models import Reminder
from tests.reminders.services.fakes import FakeUser, FakeUserSettings


@dataclass
class FakeTelegramUser:
    id: int = 1129873105
    username: str | None = "smirnovv112"
    language_code: str | None = "en"


class FakeMessage:
    def __init__(self) -> None:
        self.from_user = FakeTelegramUser()
        self.text: str | None = None
        self.answers: list[tuple[str, object]] = []

    async def answer(self, text: str, reply_markup: object = None) -> None:
        self.answers.append((text, reply_markup))


class FakeMenuUsers:
    def __init__(self, user: FakeUser | None = None) -> None:
        self.user = user or FakeUser(
            id=10,
            telegram_user_id=100,
            username=None,
            locale=None,
            settings=FakeUserSettings(),
        )
        self.get_or_create_called_with: dict[str, object] | None = None
        self.update_settings_called_with: dict[str, object] | None = None

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

    async def update_settings(
        self,
        *,
        user_id: int,
        timezone: str | None = None,
        repeat_interval_minutes: int | None = None,
    ) -> FakeUserSettings:
        self.update_settings_called_with = {
            "user_id": user_id,
            "timezone": timezone,
            "repeat_interval_minutes": repeat_interval_minutes,
        }
        if timezone is not None:
            self.user.settings.timezone = timezone
        if repeat_interval_minutes is not None:
            self.user.settings.repeat_interval_minutes = repeat_interval_minutes
        return self.user.settings


class FakeMenuReminders:
    def __init__(self, reminders: list[Reminder] | None = None) -> None:
        self.reminders = reminders or []
        self.completed_since_called_with: dict[str, object] | None = None

    async def list_active_for_user(self, *, user_id: int, limit: int) -> list[Reminder]:
        return self.reminders[:limit]

    async def list_recent_for_user(self, *, user_id: int, limit: int) -> list[Reminder]:
        return self.reminders[:limit]

    async def list_completed_since(
        self,
        *,
        user_id: int,
        since: datetime,
        limit: int,
    ) -> list[Reminder]:
        self.completed_since_called_with = {
            "user_id": user_id,
            "since": since,
            "limit": limit,
        }
        return self.reminders[:limit]


class FakeMenuUnitOfWork:
    def __init__(
        self,
        *,
        users: FakeMenuUsers | None = None,
        reminders: FakeMenuReminders | None = None,
    ) -> None:
        self.users = users or FakeMenuUsers()
        self.reminders = reminders or FakeMenuReminders()


class FakeUnitOfWorkContext:
    def __init__(self, uow: FakeMenuUnitOfWork) -> None:
        self.uow = uow

    async def __aenter__(self) -> FakeMenuUnitOfWork:
        return self.uow

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


def test_main_menu_keyboard_packs_expected_callbacks() -> None:
    keyboard = main_menu_keyboard()

    buttons = [button for row in keyboard.inline_keyboard for button in row]
    labels = [button.text for button in buttons]
    callbacks = [MenuCallback.unpack(button.callback_data) for button in buttons]

    assert labels == [
        "⚙️ Settings",
        "📌 Active reminders",
        "📋 Task history",
        "🗄️ Archive",
        "✍️ New reminder",
        "ℹ️ Help",
    ]
    assert [callback.action for callback in callbacks] == [
        MenuActionEnum.SETTINGS,
        MenuActionEnum.ACTIVE,
        MenuActionEnum.HISTORY,
        MenuActionEnum.ARCHIVE,
        MenuActionEnum.NEW_REMINDER,
        MenuActionEnum.HELP,
    ]


def test_bottom_menu_keyboard_stays_near_text_input() -> None:
    keyboard = bottom_menu_keyboard()

    assert [[button.text for button in row] for row in keyboard.keyboard] == [
        [MENU_SETTINGS_BUTTON_TEXT, MENU_ACTIVE_BUTTON_TEXT],
        [MENU_HISTORY_BUTTON_TEXT, MENU_ARCHIVE_BUTTON_TEXT],
        [MENU_NEW_REMINDER_BUTTON_TEXT, MENU_HELP_BUTTON_TEXT],
    ]
    assert keyboard.resize_keyboard is True
    assert keyboard.is_persistent is True
    assert keyboard.input_field_placeholder == "Send a reminder or choose an action"


def test_settings_keyboards_expose_exact_presets() -> None:
    timezone_keyboard = timezone_menu_keyboard("Europe/Minsk")
    repeat_keyboard = repeat_interval_menu_keyboard(5)

    timezone_callbacks = [
        MenuCallback.unpack(row[0].callback_data) for row in timezone_keyboard.inline_keyboard[:-1]
    ]
    repeat_callbacks = [
        MenuCallback.unpack(row[0].callback_data) for row in repeat_keyboard.inline_keyboard[:-1]
    ]

    assert [callback.value for callback in timezone_callbacks] == list(TIMEZONE_PRESETS)
    assert [callback.value for callback in repeat_callbacks] == [
        str(interval) for interval in REPEAT_INTERVAL_PRESETS
    ]
    assert timezone_keyboard.inline_keyboard[0][0].text == "✅ Europe/Minsk"
    assert repeat_keyboard.inline_keyboard[0][0].text == "✅ 5 min"


def test_format_reminder_list_handles_empty_and_invalid_timezone() -> None:
    reminder = Reminder(
        id=42,
        user_id=10,
        status=ReminderStatusEnum.ACTIVE,
        reminder_text="walk the dog",
        due_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
    )

    empty_message = menu.format_reminder_list(
        title="📌 Active reminders",
        empty_text="No active reminders.",
        reminders=[],
        timezone="Europe/Minsk",
        time_field="due",
    )
    message = menu.format_reminder_list(
        title="📌 Active reminders",
        empty_text="No active reminders.",
        reminders=[reminder],
        timezone="Bad/Timezone",
        time_field="due",
    )

    assert empty_message == "📌 Active reminders\n\nNo active reminders."
    assert "walk the dog" in message
    assert "2026-07-03 12:00" in message
    assert "metadata" not in message


@pytest.mark.asyncio
async def test_menu_command_creates_unknown_user_and_opens_main_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uow = FakeMenuUnitOfWork()
    message = FakeMessage()

    monkeypatch.setattr(menu, "unit_of_work", lambda session_factory: FakeUnitOfWorkContext(uow))

    await menu.handle_menu_command(
        message,  # type: ignore[arg-type]
        Settings(),
        session_factory=object(),  # type: ignore[arg-type]
    )

    assert uow.users.get_or_create_called_with == {
        "telegram_user_id": 1129873105,
        "username": "smirnovv112",
        "locale": "en",
        "timezone": "Europe/Minsk",
        "repeat_interval_minutes": 5,
    }
    assert message.answers[0][0] == menu.format_reply_menu_intro()


@pytest.mark.asyncio
async def test_reply_menu_button_opens_matching_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    uow = FakeMenuUnitOfWork()
    message = FakeMessage()
    message.text = MENU_SETTINGS_BUTTON_TEXT

    monkeypatch.setattr(menu, "unit_of_work", lambda session_factory: FakeUnitOfWorkContext(uow))

    await menu.handle_reply_menu_button(
        message,  # type: ignore[arg-type]
        Settings(),
        session_factory=object(),  # type: ignore[arg-type]
    )

    assert uow.users.get_or_create_called_with is not None
    assert len(message.answers) == 1
    assert "Settings" in message.answers[0][0]
    assert message.answers[0][1] is not None


@pytest.mark.asyncio
async def test_settings_selection_persists_repeat_interval() -> None:
    users = FakeMenuUsers()
    uow = FakeMenuUnitOfWork(users=users)

    text, reply_markup = await menu.build_menu_screen(
        action=MenuActionEnum.SET_REPEAT_INTERVAL,
        value="30",
        user=users.user,  # type: ignore[arg-type]
        settings=Settings(),
        uow=uow,
        now=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
    )

    assert users.update_settings_called_with == {
        "user_id": 10,
        "timezone": None,
        "repeat_interval_minutes": 30,
    }
    assert "🔁 Repeat interval: 30 min" in text
    assert reply_markup is not None


@pytest.mark.asyncio
async def test_archive_screen_filters_last_three_months() -> None:
    reminder = Reminder(
        id=42,
        user_id=10,
        status=ReminderStatusEnum.COMPLETED,
        reminder_text="submit report",
        due_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        completed_at=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
    )
    reminders = FakeMenuReminders([reminder])
    users = FakeMenuUsers()
    uow = FakeMenuUnitOfWork(users=users, reminders=reminders)
    now = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)

    text, _ = await menu.build_menu_screen(
        action=MenuActionEnum.ARCHIVE,
        value=None,
        user=users.user,  # type: ignore[arg-type]
        settings=Settings(),
        uow=uow,
        now=now,
    )

    assert reminders.completed_since_called_with == {
        "user_id": 10,
        "since": datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
        "limit": 10,
    }
    assert "🗄️ Completed tasks, last 3 months" in text
    assert "submit report" in text
