from __future__ import annotations

import re

SUPPORTED_DATE_LANGUAGES = ["ru", "en"]

ENGLISH_WEEKDAYS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}
ENGLISH_WEEKDAY_NAMES_PATTERN = "|".join(
    re.escape(weekday_name) for weekday_name in sorted(ENGLISH_WEEKDAYS, key=len, reverse=True)
)
ENGLISH_WEEKDAY_PHRASE_PATTERN = rf"(?:on\s+)?(?:{ENGLISH_WEEKDAY_NAMES_PATTERN})\.?"
ENGLISH_CLOCK_PATTERN = r"(?:at\s+)?\d{1,2}(?:(?::|\s+)\d{2})?\s*(?:am|pm)?"
ENGLISH_OPTIONAL_CLOCK_PATTERN = rf"(?:\s+{ENGLISH_CLOCK_PATTERN})?"

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

RUSSIAN_WEEKDAYS = {
    "понедельник": 0,
    "пн": 0,
    "вторник": 1,
    "вт": 1,
    "среда": 2,
    "среду": 2,
    "ср": 2,
    "четверг": 3,
    "чт": 3,
    "пятница": 4,
    "пятницу": 4,
    "пт": 4,
    "суббота": 5,
    "суббата": 5,
    "субботу": 5,
    "суббату": 5,
    "сб": 5,
    "воскресенье": 6,
    "вс": 6,
}
RUSSIAN_WEEKDAY_NAMES_PATTERN = "|".join(
    re.escape(weekday_name) for weekday_name in sorted(RUSSIAN_WEEKDAYS, key=len, reverse=True)
)
RUSSIAN_WEEKDAY_PHRASE_PATTERN = rf"(?:во|в)?\s*(?:{RUSSIAN_WEEKDAY_NAMES_PATTERN})"
RUSSIAN_CLOCK_PATTERN = r"(?:в\s+)?\d{1,2}(?:(?::|\s+)\d{2})?\s*(?:утра|дня|вечера|ночи)?"
RUSSIAN_OPTIONAL_CLOCK_PATTERN = rf"(?:\s+{RUSSIAN_CLOCK_PATTERN})?"

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

TEMPORAL_AMBIGUITY_PATTERNS = (
    re.compile(
        rf"\b{ENGLISH_WEEKDAY_PHRASE_PATTERN}\b{ENGLISH_OPTIONAL_CLOCK_PATTERN}\s+"
        rf"(?:or|and)\s+\b{ENGLISH_WEEKDAY_PHRASE_PATTERN}\b"
        rf"{ENGLISH_OPTIONAL_CLOCK_PATTERN}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b{ENGLISH_WEEKDAY_PHRASE_PATTERN}\b\s+{ENGLISH_CLOCK_PATTERN}\s+"
        rf"(?:or|and)\s+{ENGLISH_CLOCK_PATTERN}",
        re.IGNORECASE,
    ),
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
    re.compile(
        rf"\b{RUSSIAN_WEEKDAY_PHRASE_PATTERN}\b{RUSSIAN_OPTIONAL_CLOCK_PATTERN}\s+"
        rf"(?:или|либо|и)\s+\b{RUSSIAN_WEEKDAY_PHRASE_PATTERN}\b"
        rf"{RUSSIAN_OPTIONAL_CLOCK_PATTERN}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b{RUSSIAN_WEEKDAY_PHRASE_PATTERN}\b\s+{RUSSIAN_CLOCK_PATTERN}\s+"
        rf"(?:или|либо|и)\s+{RUSSIAN_CLOCK_PATTERN}",
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

ENGLISH_WEEKDAY_PATTERN = re.compile(
    rf"\b(?:on\s+)?(?P<weekday>{ENGLISH_WEEKDAY_NAMES_PATTERN})\.?\b"
    r"(?:\s+(?:at\s+)?(?P<hour>\d{1,2})(?:(?::|\s+)(?P<minute>\d{2}))?"
    r"\s*(?P<modifier>am|pm)?)?",
    re.IGNORECASE,
)

ENGLISH_TIME_BEFORE_WEEKDAY_PATTERN = re.compile(
    r"\b(?:at\s+)?(?P<hour>\d{1,2})(?:(?::|\s+)(?P<minute>\d{2}))?"
    rf"\s*(?P<modifier>am|pm)?\s+(?:on\s+)?(?P<weekday>{ENGLISH_WEEKDAY_NAMES_PATTERN})\.?\b",
    re.IGNORECASE,
)

RUSSIAN_WEEKDAY_PATTERN = re.compile(
    rf"\b(?:во|в)?\s*(?P<weekday>{RUSSIAN_WEEKDAY_NAMES_PATTERN})\b"
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
