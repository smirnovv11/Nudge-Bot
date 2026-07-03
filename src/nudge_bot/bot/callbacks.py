from __future__ import annotations

from aiogram.filters.callback_data import CallbackData

from nudge_bot.reminders.enums import CallbackActionEnum


class ReminderActionCallback(CallbackData, prefix="rem"):
    action: CallbackActionEnum
    reminder_id: int
    notification_id: int | None = None


class ReminderDraftCallback(CallbackData, prefix="draft"):
    action: CallbackActionEnum
    draft_id: int
