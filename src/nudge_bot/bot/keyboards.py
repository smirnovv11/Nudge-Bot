from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from nudge_bot.bot.callbacks import (
    MenuActionEnum,
    MenuCallback,
    ReminderActionCallback,
    ReminderDraftCallback,
)
from nudge_bot.reminders.enums import CallbackActionEnum

TIMEZONE_PRESETS = (
    "Europe/Minsk",
    "UTC",
    "Europe/Warsaw",
    "Europe/Moscow",
    "America/New_York",
)

REPEAT_INTERVAL_PRESETS = (5, 10, 15, 30, 60, 120)

MENU_SETTINGS_BUTTON_TEXT = "⚙️ Settings"
MENU_ACTIVE_BUTTON_TEXT = "📌 Active reminders"
MENU_HISTORY_BUTTON_TEXT = "📋 Task history"
MENU_ARCHIVE_BUTTON_TEXT = "🗄️ Archive"
MENU_NEW_REMINDER_BUTTON_TEXT = "✍️ New reminder"
MENU_HELP_BUTTON_TEXT = "ℹ️ Help"

MENU_REPLY_ACTIONS = {
    MENU_SETTINGS_BUTTON_TEXT: MenuActionEnum.SETTINGS,
    MENU_ACTIVE_BUTTON_TEXT: MenuActionEnum.ACTIVE,
    MENU_HISTORY_BUTTON_TEXT: MenuActionEnum.HISTORY,
    MENU_ARCHIVE_BUTTON_TEXT: MenuActionEnum.ARCHIVE,
    MENU_NEW_REMINDER_BUTTON_TEXT: MenuActionEnum.NEW_REMINDER,
    MENU_HELP_BUTTON_TEXT: MenuActionEnum.HELP,
}


def reminder_actions_keyboard(
    reminder_id: int,
    notification_id: int | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Read",
                    callback_data=ReminderActionCallback(
                        action=CallbackActionEnum.READ,
                        reminder_id=reminder_id,
                        notification_id=notification_id,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="🔁 Repeat",
                    callback_data=ReminderActionCallback(
                        action=CallbackActionEnum.REPEAT,
                        reminder_id=reminder_id,
                        notification_id=notification_id,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="🕒 Choose time",
                    callback_data=ReminderActionCallback(
                        action=CallbackActionEnum.CHOOSE_TIME,
                        reminder_id=reminder_id,
                        notification_id=notification_id,
                    ).pack(),
                ),
            ]
        ]
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _menu_button("⚙️ Settings", MenuActionEnum.SETTINGS),
                _menu_button("📌 Active reminders", MenuActionEnum.ACTIVE),
            ],
            [
                _menu_button("📋 Task history", MenuActionEnum.HISTORY),
                _menu_button("🗄️ Archive", MenuActionEnum.ARCHIVE),
            ],
            [
                _menu_button("✍️ New reminder", MenuActionEnum.NEW_REMINDER),
                _menu_button("ℹ️ Help", MenuActionEnum.HELP),
            ],
        ]
    )


def open_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_menu_button("📋 Open menu", MenuActionEnum.MAIN)]]
    )


def bottom_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=MENU_SETTINGS_BUTTON_TEXT),
                KeyboardButton(text=MENU_ACTIVE_BUTTON_TEXT),
            ],
            [
                KeyboardButton(text=MENU_HISTORY_BUTTON_TEXT),
                KeyboardButton(text=MENU_ARCHIVE_BUTTON_TEXT),
            ],
            [
                KeyboardButton(text=MENU_NEW_REMINDER_BUTTON_TEXT),
                KeyboardButton(text=MENU_HELP_BUTTON_TEXT),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Send a reminder or choose an action",
        is_persistent=True,
    )


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _menu_button("🌍 Timezone", MenuActionEnum.TIMEZONE),
                _menu_button("🔁 Repeat interval", MenuActionEnum.REPEAT_INTERVAL),
            ],
            [_menu_button("⬅️ Back", MenuActionEnum.MAIN)],
        ]
    )


def timezone_menu_keyboard(current_timezone: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _menu_button(
                    _selected_label(timezone, current_timezone),
                    MenuActionEnum.SET_TIMEZONE,
                    timezone,
                )
            ]
            for timezone in TIMEZONE_PRESETS
        ]
        + [[_menu_button("⬅️ Back", MenuActionEnum.SETTINGS)]]
    )


def repeat_interval_menu_keyboard(current_interval: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _menu_button(
                    _selected_label(f"{minutes} min", str(current_interval), str(minutes)),
                    MenuActionEnum.SET_REPEAT_INTERVAL,
                    str(minutes),
                )
            ]
            for minutes in REPEAT_INTERVAL_PRESETS
        ]
        + [[_menu_button("⬅️ Back", MenuActionEnum.SETTINGS)]]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_menu_button("⬅️ Back", MenuActionEnum.MAIN)]])


def draft_confirmation_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Create",
                    callback_data=ReminderDraftCallback(
                        action=CallbackActionEnum.CONFIRM,
                        draft_id=draft_id,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="✖️ Cancel",
                    callback_data=ReminderDraftCallback(
                        action=CallbackActionEnum.CANCEL,
                        draft_id=draft_id,
                    ).pack(),
                ),
            ]
        ]
    )


def _menu_button(
    text: str,
    action: MenuActionEnum,
    value: str | None = None,
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=MenuCallback(action=action, value=value).pack(),
    )


def _selected_label(label: str, current_value: str, value: str | None = None) -> str:
    if (value or label) == current_value:
        return f"✅ {label}"
    return label


def edit_time_cancel_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Cancel",
                    callback_data=ReminderDraftCallback(
                        action=CallbackActionEnum.CANCEL,
                        draft_id=draft_id,
                    ).pack(),
                ),
            ]
        ]
    )
