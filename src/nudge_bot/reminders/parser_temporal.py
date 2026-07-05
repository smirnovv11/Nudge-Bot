from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from dateparser.search import search_dates

from nudge_bot.reminders.parser_patterns import (
    ENGLISH_TIME_BEFORE_WEEKDAY_PATTERN,
    ENGLISH_WEEKDAY_PATTERN,
    ENGLISH_WEEKDAYS,
    RUSSIAN_DAY_OFFSETS,
    RUSSIAN_DAY_PARTS,
    RUSSIAN_DAY_PATTERN,
    RUSSIAN_NUMBER_WORDS,
    RUSSIAN_NUMERIC_DATE_PATTERN,
    RUSSIAN_RELATIVE_PATTERNS,
    RUSSIAN_TIME_ONLY_PATTERNS,
    RUSSIAN_WEEKDAY_PATTERN,
    RUSSIAN_WEEKDAYS,
    SUPPORTED_DATE_LANGUAGES,
    TEMPORAL_AMBIGUITY_PATTERNS,
    UNSUPPORTED_NUMERIC_DATEPARSER_PATTERN,
)

CONFIDENT_PARSE_THRESHOLD = 0.75


@dataclass(frozen=True)
class TemporalMatch:
    matched_text: str
    start: int
    end: int
    due_at: datetime | None
    confidence: float
    is_ambiguous: bool = False

    @property
    def needs_confirmation(self) -> bool:
        return self.is_ambiguous or self.confidence < CONFIDENT_PARSE_THRESHOLD


class TemporalRule(Protocol):
    def match(self, text: str, now: datetime, timezone: str) -> TemporalMatch | None:
        """Return the first temporal match this rule owns, or None."""


@dataclass(frozen=True)
class WeekdayRuleConfig:
    pattern: re.Pattern[str]
    weekdays: dict[str, int]
    leading_time_pattern: re.Pattern[str] | None = None
    day_parts: dict[str, tuple[int, int]] | None = None


class TemporalParser:
    def __init__(self, rules: tuple[TemporalRule, ...]) -> None:
        self._rules = rules

    def match(self, text: str, now: datetime, timezone: str) -> TemporalMatch | None:
        for rule in self._rules:
            match = rule.match(text, now, timezone)
            if match is not None:
                return match

        return None


class TemporalAmbiguityRule:
    def match(self, text: str, now: datetime, timezone: str) -> TemporalMatch | None:
        for pattern in TEMPORAL_AMBIGUITY_PATTERNS:
            if pattern.search(text) is None:
                continue

            return TemporalMatch(
                matched_text=text,
                start=0,
                end=len(text),
                due_at=None,
                confidence=0.35,
                is_ambiguous=True,
            )

        return None


class RussianRelativeOffsetRule:
    def match(self, text: str, now: datetime, timezone: str) -> TemporalMatch | None:
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


class RussianDayPhraseRule:
    def match(self, text: str, now: datetime, timezone: str) -> TemporalMatch | None:
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


class WeekdayRule:
    def __init__(self, config: WeekdayRuleConfig) -> None:
        self._config = config

    def match(self, text: str, now: datetime, timezone: str) -> TemporalMatch | None:
        match = self._find_match(text)
        if match is None:
            return None

        weekday = self._config.weekdays[match.group("weekday").lower()]
        hour_text = match.group("hour")
        day_part = match.groupdict().get("part")
        modifier = match.group("modifier")

        if hour_text is not None:
            clock = _safe_parse_clock(hour_text, match.group("minute"), modifier)
            if clock is None:
                return None
            hour, minute = clock
            confidence = 0.85 if match.group("minute") or modifier is not None else 0.72
        elif day_part is not None and self._config.day_parts is not None:
            hour, minute = self._config.day_parts[day_part.lower()]
            confidence = 0.8
        else:
            hour, minute = 0, 0
            confidence = 0.6

        due_at = _nearest_future_weekday(
            now,
            weekday=weekday,
            hour=hour,
            minute=minute,
        )
        return TemporalMatch(
            matched_text=match.group(0),
            start=match.start(),
            end=match.end(),
            due_at=due_at,
            confidence=confidence,
        )

    def _find_match(self, text: str) -> re.Match[str] | None:
        match = self._config.pattern.search(text)
        if self._config.leading_time_pattern is None:
            return match

        leading_match = self._config.leading_time_pattern.search(text)
        if leading_match is None:
            return match
        if match is None:
            return leading_match
        if leading_match.start() < match.start():
            return leading_match
        if leading_match.start() == match.start() and leading_match.end() > match.end():
            return leading_match

        return match


class RussianNumericDateRule:
    def match(self, text: str, now: datetime, timezone: str) -> TemporalMatch | None:
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


class RussianTimeOnlyRule:
    def match(self, text: str, now: datetime, timezone: str) -> TemporalMatch | None:
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


class DateparserFallbackRule:
    def match(self, text: str, now: datetime, timezone: str) -> TemporalMatch | None:
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


DEFAULT_TEMPORAL_PARSER = TemporalParser(
    rules=(
        TemporalAmbiguityRule(),
        RussianRelativeOffsetRule(),
        RussianDayPhraseRule(),
        WeekdayRule(
            WeekdayRuleConfig(
                pattern=ENGLISH_WEEKDAY_PATTERN,
                weekdays=ENGLISH_WEEKDAYS,
                leading_time_pattern=ENGLISH_TIME_BEFORE_WEEKDAY_PATTERN,
            )
        ),
        WeekdayRule(
            WeekdayRuleConfig(
                pattern=RUSSIAN_WEEKDAY_PATTERN,
                weekdays=RUSSIAN_WEEKDAYS,
                day_parts=RUSSIAN_DAY_PARTS,
            )
        ),
        RussianNumericDateRule(),
        RussianTimeOnlyRule(),
        DateparserFallbackRule(),
    )
)


def _find_temporal_match(text: str, now: datetime, timezone: str) -> TemporalMatch | None:
    return DEFAULT_TEMPORAL_PARSER.match(text, now, timezone)


def _nearest_future_weekday(
    now: datetime,
    *,
    weekday: int,
    hour: int,
    minute: int,
) -> datetime:
    days_ahead = (weekday - now.weekday()) % 7
    due_at = (now + timedelta(days=days_ahead)).replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )
    if due_at <= now:
        due_at += timedelta(days=7)

    return due_at


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
    if lowered == "am":
        return (0 if hour == 12 else hour), minute
    if lowered == "pm" and 1 <= hour <= 11:
        return hour + 12, minute
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
