from __future__ import annotations

from typing import Literal

from aiogram.filters.callback_data import CallbackData


class ReminderActionCallback(CallbackData, prefix="rem"):
    action: Literal["read", "repeat", "choose_time"]
    reminder_id: int
    notification_id: int | None = None


class ReminderDraftCallback(CallbackData, prefix="draft"):
    action: Literal["confirm", "edit_time", "edit_text", "cancel"]
    draft_id: int
