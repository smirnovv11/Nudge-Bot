from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nudge_bot.reminders.enums import ReminderStatus


@dataclass(frozen=True)
class ReminderToSend:
    reminder_id: int
    user_id: int
    telegram_user_id: int
    reminder_text: str
    due_at: datetime
    repeat_interval_minutes: int
    is_auto_repeat: bool = False
    previous_telegram_message_id: int | None = None


@dataclass(frozen=True)
class ReminderResult:
    reminder_id: int
    status: ReminderStatus
    changed: bool
    due_at: datetime | None = None


@dataclass(frozen=True)
class ReminderDeliveryAttempt:
    id: int
    reminder_id: int
    attempt_no: int
