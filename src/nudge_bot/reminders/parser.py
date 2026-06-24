from __future__ import annotations

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

    matches = search_dates(
        normalized_text,
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
    confidence = _confidence_for_text(normalized_text)
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


def _confidence_for_text(text: str) -> float:
    lowered = text.lower()
    strong_markers = (
        " in ",
        " tomorrow",
        " today",
        " at ",
    )
    if any(marker in f" {lowered} " for marker in strong_markers):
        return 0.85
    return 0.6


def _strip_common_reminder_prefix(text: str) -> str:
    lowered = text.lower()
    for prefix in ("remind me to ", "remind me "):
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip() or text
    return text


def _strip_date_phrase(text: str, matched_text: str) -> str:
    stripped = text.replace(matched_text, "", 1).strip(" ,.;:-")
    return stripped or text
