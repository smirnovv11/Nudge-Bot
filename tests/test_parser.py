from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nudge_bot.reminders.parser import parse_reminder_text

NOW = datetime(2026, 6, 24, 12, 0, tzinfo=ZoneInfo("Europe/Minsk"))


def test_parse_relative_reminder_confident() -> None:
    draft = parse_reminder_text(
        "walk the dog in 20 minutes",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "reminder"
    assert draft.due_at is not None
    assert draft.reminder_text == "walk the dog"
    assert draft.due_at.hour == 12
    assert draft.due_at.minute == 20
    assert draft.parse_confidence >= 0.75
    assert draft.needs_confirmation is False


def test_parse_russian_relative_reminder_confident() -> None:
    draft = parse_reminder_text(
        "погулять с собакой через 20 мин",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "reminder"
    assert draft.reminder_text == "погулять с собакой"
    assert draft.due_at is not None
    assert draft.due_at.hour == 12
    assert draft.due_at.minute == 20
    assert draft.parse_confidence >= 0.75
    assert draft.needs_confirmation is False


def test_parse_russian_tomorrow_with_hour_confident() -> None:
    draft = parse_reminder_text(
        "напомни купить молоко завтра в 9",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "reminder"
    assert draft.reminder_text == "купить молоко"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-25"
    assert draft.due_at.hour == 9
    assert draft.due_at.minute == 0
    assert draft.parse_confidence >= 0.75
    assert draft.needs_confirmation is False


def test_parse_absolute_date_without_time_needs_confirmation() -> None:
    draft = parse_reminder_text(
        "забрать справку 26 февраля 2027 года",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "reminder"
    assert draft.reminder_text == "забрать справку"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2027-02-26"
    assert draft.parse_confidence < 0.75
    assert draft.needs_confirmation is True


def test_explicit_note_marker_does_not_create_reminder() -> None:
    draft = parse_reminder_text(
        "заметка: забрать справку 26 февраля 2027 года",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "note"
    assert draft.reminder_text == "забрать справку 26 февраля 2027 года"
    assert draft.due_at is None
    assert draft.needs_confirmation is False


def test_unknown_text_needs_confirmation() -> None:
    draft = parse_reminder_text("купить молоко", now=NOW, timezone="Europe/Minsk")

    assert draft.intent_kind == "unknown"
    assert draft.reminder_text == "купить молоко"
    assert draft.due_at is None
    assert draft.needs_confirmation is True


def test_empty_text_needs_confirmation() -> None:
    draft = parse_reminder_text("", now=NOW, timezone="Europe/Minsk")

    assert draft.intent_kind == "unknown"
    assert draft.due_at is None
    assert draft.needs_confirmation is True
