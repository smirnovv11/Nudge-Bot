from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from nudge_bot.reminders.parser import ParsedReminderDraft
from nudge_bot.storage.models import Draft, Reminder

TextReminderOutcome = Literal["created", "draft", "unknown", "note"]
DraftActionOutcome = Literal[
    "confirmed",
    "cancelled",
    "already_confirmed",
    "already_cancelled",
    "expired",
]


@dataclass(frozen=True)
class TextReminderResult:
    outcome: TextReminderOutcome
    user_id: int
    parsed: ParsedReminderDraft
    display_timezone: str
    reminder: Reminder | None = None
    draft: Draft | None = None


@dataclass(frozen=True)
class DraftActionResult:
    outcome: DraftActionOutcome
    draft: Draft
    changed: bool
    display_timezone: str | None = None
    reminder: Reminder | None = None
