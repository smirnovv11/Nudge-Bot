from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from nudge_bot.reminders.enums import ParserIntentEnum
from nudge_bot.reminders.parser_temporal import _find_temporal_match

NOTE_MARKERS = ("заметка:", "сохрани:", "note:", "save:")
REMINDER_PREFIXES = ("remind me to ", "remind me ", "напомни мне ", "напомни ")


@dataclass(frozen=True)
class ParsedReminderDraft:
    input_text: str
    reminder_text: str | None
    due_at: datetime | None
    parse_confidence: float
    intent_kind: ParserIntentEnum
    needs_confirmation: bool


def parse_reminder_text(text: str, *, now: datetime, timezone: str) -> ParsedReminderDraft:
    normalized_text = text.strip()
    if not normalized_text:
        return ParsedReminderDraft(
            input_text=text,
            reminder_text=None,
            due_at=None,
            parse_confidence=0.0,
            intent_kind=ParserIntentEnum.UNKNOWN,
            needs_confirmation=True,
        )

    note_text = _strip_explicit_note_marker(normalized_text)
    if note_text is not None:
        return ParsedReminderDraft(
            input_text=text,
            reminder_text=note_text,
            due_at=None,
            parse_confidence=1.0,
            intent_kind=ParserIntentEnum.NOTE,
            needs_confirmation=False,
        )

    reminder_source_text = _strip_common_reminder_prefix(normalized_text)
    temporal_match = _find_temporal_match(normalized_text, now, timezone)
    if temporal_match is None:
        return ParsedReminderDraft(
            input_text=text,
            reminder_text=normalized_text,
            due_at=None,
            parse_confidence=0.2,
            intent_kind=ParserIntentEnum.UNKNOWN,
            needs_confirmation=True,
        )

    if temporal_match.due_at is None:
        return ParsedReminderDraft(
            input_text=text,
            reminder_text=reminder_source_text,
            due_at=None,
            parse_confidence=temporal_match.confidence,
            intent_kind=ParserIntentEnum.REMINDER,
            needs_confirmation=True,
        )

    reminder_text = _strip_date_phrase(
        reminder_source_text,
        temporal_match.matched_text,
        start=temporal_match.start,
        end=temporal_match.end,
    )
    return ParsedReminderDraft(
        input_text=text,
        reminder_text=reminder_text,
        due_at=temporal_match.due_at,
        parse_confidence=temporal_match.confidence,
        intent_kind=ParserIntentEnum.REMINDER,
        needs_confirmation=temporal_match.needs_confirmation,
    )


def _strip_explicit_note_marker(text: str) -> str | None:
    lowered = text.lower()
    for marker in NOTE_MARKERS:
        if lowered.startswith(marker):
            return text[len(marker) :].strip() or text
    return None


def _strip_common_reminder_prefix(text: str) -> str:
    lowered = text.lower()
    for prefix in REMINDER_PREFIXES:
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip() or text
    return text


def _strip_date_phrase(text: str, matched_text: str, *, start: int, end: int) -> str:
    if 0 <= start < end <= len(text):
        stripped = f"{text[:start]} {text[end:]}".strip(" ,.;:-")
    else:
        stripped = text.replace(matched_text, "", 1).strip(" ,.;:-")
    return re.sub(r"\s+", " ", stripped).strip() or text
