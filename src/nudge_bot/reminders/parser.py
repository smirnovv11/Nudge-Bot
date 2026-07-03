from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from dateparser.search import search_dates

from nudge_bot.reminders.enums import ParserIntentEnum

CONFIDENT_PARSE_THRESHOLD = 0.75
SUPPORTED_DATE_LANGUAGES = ["ru", "en"]

NOTE_MARKERS = ("заметка:", "сохрани:", "note:", "save:")
REMINDER_PREFIXES = ("remind me to ", "remind me ", "напомни мне ", "напомни ")

RUSSIAN_DAY_OFFSETS = {
    "сегодня": 0,
    "завтра": 1,
    "послезавтра": 2,
}

RUSSIAN_DAY_PARTS = {
    "утром": (9, 0),
    "днем": (13, 0),
    "днём": (13, 0),
    "вечером": (19, 0),
    "ночью": (22, 0),
}

RUSSIAN_NUMBER_WORDS = {
    "один": 1,
    "одна": 1,
    "одно": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
}

RUSSIAN_AMBIGUITY_PATTERNS = (
    re.compile(
        r"\b(?:сегодня|завтра|послезавтра)\s+(?:или|либо)\s+"
        r"(?:сегодня|завтра|послезавтра)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:в\s*)?\d{1,2}(?::\d{2})?\s*(?:утра|дня|вечера|ночи)?\s+"
        r"(?:или|либо)\s+(?:в\s*)?\d{1,2}(?::\d{2})?\s*"
        r"(?:утра|дня|вечера|ночи)?\b",
        re.IGNORECASE,
    ),
)

RUSSIAN_RELATIVE_PATTERNS = (
    re.compile(r"\bчерез\s+пол[-\s]?часа?\b", re.IGNORECASE),
    re.compile(
        r"\bчерез\s+(?:(?P<number>\d+|[а-яё]+)\s*)?"
        r"(?P<unit>мин\.?|минут[уы]?|м\b|час(?:ик)?(?:а|ов)?|ч\b)\b",
        re.IGNORECASE,
    ),
)

RUSSIAN_DAY_PATTERN = re.compile(
    r"\b(?P<day>сегодня|завтра|послезавтра)\b"
    r"(?:\s+(?P<part>утром|днем|днём|вечером|ночью))?"
    r"(?:\s+(?:в\s+)?(?P<hour>\d{1,2})(?:(?::|\s+)(?P<minute>\d{2}))?"
    r"\s*(?P<modifier>утра|дня|вечера|ночи)?)?",
    re.IGNORECASE,
)

RUSSIAN_NUMERIC_DATE_PATTERN = re.compile(
    r"(?<!\d)(?P<day>\d{1,2})[.-](?P<month>\d{1,2})(?!\d)"
    r"(?:\s+(?:в\s+)?(?P<hour>\d{1,2})(?:(?::|\s+)(?P<minute>\d{2}))?)?",
    re.IGNORECASE,
)

RUSSIAN_TIME_ONLY_PATTERNS = (
    re.compile(
        r"\bв\s+(?P<hour>\d{1,2})\s+(?P<minute>\d{2})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bв\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?"
        r"\s*(?P<modifier>утра|дня|вечера|ночи)?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?P<hour>\d{1,2}):(?P<minute>\d{2})\b", re.IGNORECASE),
    re.compile(
        r"(?<!\d)(?P<hour>\d{1,2})\s+(?P<minute>\d{2})(?!\d)\s*$",
        re.IGNORECASE,
    ),
)

UNSUPPORTED_NUMERIC_DATEPARSER_PATTERN = re.compile(r"^\d{1,2}\s+\d{2,4}$")


@dataclass(frozen=True)
class ParsedReminderDraft:
    input_text: str
    reminder_text: str | None
    due_at: datetime | None
    parse_confidence: float
    intent_kind: ParserIntentEnum
    needs_confirmation: bool


@dataclass(frozen=True)
class TemporalMatch:
    matched_text: str
    start: int
    end: int
    due_at: datetime
    confidence: float

    @property
    def needs_confirmation(self) -> bool:
        return self.confidence < CONFIDENT_PARSE_THRESHOLD


TemporalRule = Callable[[str, datetime], TemporalMatch | None]


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

    if _has_conflicting_temporal_phrase(normalized_text):
        return ParsedReminderDraft(
            input_text=text,
            reminder_text=_strip_common_reminder_prefix(normalized_text),
            due_at=None,
            parse_confidence=0.35,
            intent_kind=ParserIntentEnum.REMINDER,
            needs_confirmation=True,
        )

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

    reminder_source_text = _strip_common_reminder_prefix(normalized_text)
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


def _find_temporal_match(text: str, now: datetime, timezone: str) -> TemporalMatch | None:
    for rule in _TEMPORAL_RULES:
        match = rule(text, now)
        if match is not None:
            return match

    return _match_with_dateparser(text, now, timezone)


def _match_russian_relative_offset(text: str, now: datetime) -> TemporalMatch | None:
    half_hour_match = RUSSIAN_RELATIVE_PATTERNS[0].search(text)
    if half_hour_match is not None:
        return TemporalMatch(
            matched_text=half_hour_match.group(0),
            start=half_hour_match.start(),
            end=half_hour_match.end(),
            due_at=now + timedelta(minutes=30),
            confidence=0.9,
        )

    match = RUSSIAN_RELATIVE_PATTERNS[1].search(text)
    if match is None:
        return None

    amount = _parse_russian_number(match.group("number")) or 1
    unit = match.group("unit").lower().rstrip(".")
    if unit.startswith(("м", "мин")):
        due_at = now + timedelta(minutes=amount)
    else:
        due_at = now + timedelta(hours=amount)

    return TemporalMatch(
        matched_text=match.group(0),
        start=match.start(),
        end=match.end(),
        due_at=due_at,
        confidence=0.9,
    )


def _match_russian_day_phrase(text: str, now: datetime) -> TemporalMatch | None:
    match = RUSSIAN_DAY_PATTERN.search(text)
    if match is None:
        return None

    day = match.group("day").lower()
    base = now + timedelta(days=RUSSIAN_DAY_OFFSETS[day])
    hour_text = match.group("hour")
    day_part = match.group("part")
    modifier = match.group("modifier")

    if hour_text is not None:
        clock = _safe_parse_clock(hour_text, match.group("minute"), modifier)
        if clock is None:
            return None
        hour, minute = clock
        confidence = 0.85
    elif day_part is not None:
        hour, minute = RUSSIAN_DAY_PARTS[day_part.lower()]
        confidence = 0.8
    else:
        hour, minute = 0, 0
        confidence = 0.6

    return TemporalMatch(
        matched_text=match.group(0),
        start=match.start(),
        end=match.end(),
        due_at=base.replace(hour=hour, minute=minute, second=0, microsecond=0),
        confidence=confidence,
    )


def _match_russian_time_only(text: str, now: datetime) -> TemporalMatch | None:
    for pattern in RUSSIAN_TIME_ONLY_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue

        clock = _safe_parse_clock(
            match.group("hour"),
            match.group("minute"),
            match.groupdict().get("modifier"),
        )
        if clock is None:
            continue
        hour, minute = clock
        due_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due_at <= now:
            due_at += timedelta(days=1)

        confidence = 0.8 if match.groupdict().get("modifier") or match.group("minute") else 0.72
        return TemporalMatch(
            matched_text=match.group(0),
            start=match.start(),
            end=match.end(),
            due_at=due_at,
            confidence=confidence,
        )

    return None


def _match_russian_numeric_date(text: str, now: datetime) -> TemporalMatch | None:
    match = RUSSIAN_NUMERIC_DATE_PATTERN.search(text)
    if match is None:
        return None

    day = int(match.group("day"))
    month = int(match.group("month"))
    hour_text = match.group("hour")
    minute_text = match.group("minute")

    if hour_text is not None:
        clock = _safe_parse_clock(hour_text, minute_text, modifier=None)
        if clock is None:
            return None
        hour, minute = clock
        confidence = 0.85
    else:
        hour, minute = 0, 0
        confidence = 0.6

    try:
        due_at = now.replace(
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
    except ValueError:
        return None

    if due_at <= now:
        try:
            due_at = due_at.replace(year=due_at.year + 1)
        except ValueError:
            return None

    return TemporalMatch(
        matched_text=match.group(0),
        start=match.start(),
        end=match.end(),
        due_at=due_at,
        confidence=confidence,
    )


def _match_with_dateparser(text: str, now: datetime, timezone: str) -> TemporalMatch | None:
    matches = search_dates(
        text,
        languages=SUPPORTED_DATE_LANGUAGES,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": now,
            "TIMEZONE": timezone,
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )
    if not matches:
        return None

    for matched_text, parsed_due_at in reversed(matches):
        if _is_unsupported_numeric_dateparser_match(matched_text):
            continue

        start = text.lower().find(matched_text.lower())
        if start < 0:
            start = 0
        end = start + len(matched_text)
        parsed_due_at = _apply_colloquial_hour(parsed_due_at, matched_text)
        confidence = _confidence_for_dateparser_match(matched_text)
        return TemporalMatch(
            matched_text=matched_text,
            start=start,
            end=end,
            due_at=parsed_due_at,
            confidence=confidence,
        )

    return None


_TEMPORAL_RULES: tuple[TemporalRule, ...] = (
    _match_russian_relative_offset,
    _match_russian_day_phrase,
    _match_russian_numeric_date,
    _match_russian_time_only,
)


def _strip_explicit_note_marker(text: str) -> str | None:
    lowered = text.lower()
    for marker in NOTE_MARKERS:
        if lowered.startswith(marker):
            return text[len(marker) :].strip() or text
    return None


def _has_conflicting_temporal_phrase(text: str) -> bool:
    return any(pattern.search(text) for pattern in RUSSIAN_AMBIGUITY_PATTERNS)


def _parse_russian_number(value: str | None) -> int | None:
    if value is None:
        return None
    lowered = value.lower()
    if lowered.isdigit():
        return int(lowered)
    return RUSSIAN_NUMBER_WORDS.get(lowered)


def _parse_clock(
    hour_text: str,
    minute_text: str | None,
    modifier: str | None,
) -> tuple[int, int]:
    hour = int(hour_text)
    minute = int(minute_text or 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time: {hour_text}:{minute_text or '00'}")

    if modifier is None:
        return hour, minute

    lowered = modifier.lower()
    if lowered == "утра":
        return (0 if hour == 12 else hour), minute
    if lowered in {"дня", "вечера"} and 1 <= hour <= 11:
        return hour + 12, minute
    if lowered == "ночи":
        if hour == 12:
            return 0, minute
        if 6 <= hour <= 11:
            return hour + 12, minute

    return hour, minute


def _safe_parse_clock(
    hour_text: str,
    minute_text: str | None,
    modifier: str | None,
) -> tuple[int, int] | None:
    try:
        return _parse_clock(hour_text, minute_text, modifier)
    except ValueError:
        return None


def _confidence_for_dateparser_match(matched_text: str) -> float:
    if _has_relative_offset(matched_text) or _has_explicit_time(matched_text):
        return 0.85
    return 0.6


def _is_unsupported_numeric_dateparser_match(matched_text: str) -> bool:
    return bool(UNSUPPORTED_NUMERIC_DATEPARSER_PATTERN.fullmatch(matched_text.strip()))


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
