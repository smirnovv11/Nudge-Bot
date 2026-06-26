from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from dateparser.search import search_dates


@dataclass(frozen=True)
class ParsedReminderDraft:
    input_text: str
    reminder_text: str | None
    due_at: datetime | None
    parse_confidence: float
    intent_kind: Literal["reminder", "note", "unknown"]
    needs_confirmation: bool


def parse_reminder_text(text: str, *, now: datetime, timezone: str) -> ParsedReminderDraft:
    normalized_text = text.strip()
    if not normalized_text:
        return ParsedReminderDraft(
            input_text=text,
            reminder_text=None,
            due_at=None,
            parse_confidence=0.0,
            intent_kind="unknown",
            needs_confirmation=True,
        )

    note_text = _strip_explicit_note_marker(normalized_text)
    if note_text is not None:
        return ParsedReminderDraft(
            input_text=text,
            reminder_text=note_text,
            due_at=None,
            parse_confidence=1.0,
            intent_kind="note",
            needs_confirmation=False,
        )

    matches = search_dates(
        normalized_text,
        languages=["ru", "en"],
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": now,
            "TIMEZONE": timezone,
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )

    if not matches:
        return ParsedReminderDraft(
            input_text=text,
            reminder_text=normalized_text,
            due_at=None,
            parse_confidence=0.2,
            intent_kind="unknown",
            needs_confirmation=True,
        )

    matched_text, parsed_due_at = matches[-1]
    parsed_due_at = _apply_colloquial_hour(parsed_due_at, matched_text)
    confidence = _confidence_for_match(matched_text)
    return ParsedReminderDraft(
        input_text=text,
        reminder_text=_strip_date_phrase(
            _strip_common_reminder_prefix(normalized_text),
            matched_text,
        ),
        due_at=parsed_due_at,
        parse_confidence=confidence,
        intent_kind="reminder",
        needs_confirmation=confidence < 0.75,
    )


def _strip_explicit_note_marker(text: str) -> str | None:
    lowered = text.lower()
    for marker in ("заметка:", "сохрани:", "note:", "save:"):
        if lowered.startswith(marker):
            return text[len(marker) :].strip() or text
    return None


def _confidence_for_match(matched_text: str) -> float:
    if _has_relative_offset(matched_text) or _has_explicit_time(matched_text):
        return 0.85
    return 0.6


def _has_relative_offset(text: str) -> bool:
    lowered = text.lower()
    return bool(re.search(r"\b(in|через)\s+\d+", lowered))


def _has_explicit_time(text: str) -> bool:
    lowered = text.lower()
    return bool(
        re.search(r"\b(?:at|в)\s+\d{1,2}(?::\d{2})?\b", lowered)
        or re.search(r"\b\d{1,2}:\d{2}\b", lowered)
    )


def _apply_colloquial_hour(parsed_due_at: datetime, matched_text: str) -> datetime:
    match = re.search(
        r"\b(?:at|в)\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\b",
        matched_text.lower(),
    )
    if not match:
        return parsed_due_at

    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return parsed_due_at

    return parsed_due_at.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _strip_common_reminder_prefix(text: str) -> str:
    lowered = text.lower()
    for prefix in ("remind me to ", "remind me ", "напомни мне ", "напомни "):
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip() or text
    return text


def _strip_date_phrase(text: str, matched_text: str) -> str:
    stripped = text.replace(matched_text, "", 1).strip(" ,.;:-")
    return stripped or text
