from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from nudge_bot.reminders.parser import ParsedReminderDraft, parse_reminder_text


@dataclass(frozen=True)
class TextReminderInput:
    text: str
    now: datetime
    timezone: str


class ReminderInputStrategy(Protocol):
    def parse(self, reminder_input: TextReminderInput) -> ParsedReminderDraft:
        """Convert one incoming user input into a parsed reminder draft."""


class TextReminderInputStrategy:
    def parse(self, reminder_input: TextReminderInput) -> ParsedReminderDraft:
        return parse_reminder_text(
            reminder_input.text,
            now=reminder_input.now,
            timezone=reminder_input.timezone,
        )
