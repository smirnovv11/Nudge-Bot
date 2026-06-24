from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nudge_bot.reminders.enums import ReminderStatus


@dataclass(frozen=True)
class ReminderToSend:
    reminder_id: int
    user_id: int
    reminder_text: str
    due_at: datetime


@dataclass(frozen=True)
class ReminderResult:
    reminder_id: int
    status: ReminderStatus
    changed: bool
