from __future__ import annotations

from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from nudge_bot.reminders.enums import CallbackActionEnum


class MenuActionEnum(StrEnum):
    MAIN = "main"
    SETTINGS = "settings"
    TIMEZONE = "timezone"
    SET_TIMEZONE = "set_timezone"
    REPEAT_INTERVAL = "repeat_interval"
    SET_REPEAT_INTERVAL = "set_repeat_interval"
    HISTORY = "history"
    ARCHIVE = "archive"
    ACTIVE = "active"
    VIEW_REMINDER = "view_reminder"
    NEW_REMINDER = "new_reminder"
    HELP = "help"


class MenuCallback(CallbackData, prefix="menu"):
    action: MenuActionEnum
    value: str | None = None


class ReminderActionCallback(CallbackData, prefix="rem"):
    action: CallbackActionEnum
    reminder_id: int
    notification_id: int | None = None


class ReminderDraftCallback(CallbackData, prefix="draft"):
    action: CallbackActionEnum
    draft_id: int
