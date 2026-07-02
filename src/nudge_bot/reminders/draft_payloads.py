from __future__ import annotations

from typing import Any

from nudge_bot.storage.models import Draft

EDIT_TIME_CALLBACK_KEY = "callback_key"
EDIT_TIME_NOTIFICATION_ID = "notification_id"
EDIT_TIME_REMINDER_ID = "reminder_id"
EDIT_TIME_TIMEZONE = "timezone"


def edit_time_payload(
    *,
    reminder_id: int,
    notification_id: int | None,
    callback_key: str,
    timezone: str,
) -> dict[str, Any]:
    return {
        EDIT_TIME_CALLBACK_KEY: callback_key,
        EDIT_TIME_NOTIFICATION_ID: notification_id,
        EDIT_TIME_REMINDER_ID: reminder_id,
        EDIT_TIME_TIMEZONE: timezone,
    }


def edit_time_reminder_id(draft: Draft) -> int | None:
    reminder_id = draft.payload.get(EDIT_TIME_REMINDER_ID)
    return reminder_id if isinstance(reminder_id, int) else None
