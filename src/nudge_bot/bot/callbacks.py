from __future__ import annotations

from aiogram.filters.callback_data import CallbackData

from nudge_bot.reminders.enums import CallbackAction


class ReminderActionCallback(CallbackData, prefix="rem"):
    action: CallbackAction
    reminder_id: int
    notification_id: int | None = None


class ReminderDraftCallback(CallbackData, prefix="draft"):
    action: CallbackAction
    draft_id: int
