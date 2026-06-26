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


def test_parse_russian_relative_hour_word_confident() -> None:
    draft = parse_reminder_text(
        "проверить духовку через час",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "reminder"
    assert draft.reminder_text == "проверить духовку"
    assert draft.due_at is not None
    assert draft.due_at.hour == 13
    assert draft.due_at.minute == 0
    assert draft.parse_confidence >= 0.75
    assert draft.needs_confirmation is False


def test_parse_russian_relative_declension_and_abbreviation_confident() -> None:
    draft = parse_reminder_text(
        "выпить воду через 2 часа",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "reminder"
    assert draft.reminder_text == "выпить воду"
    assert draft.due_at is not None
    assert draft.due_at.hour == 14
    assert draft.due_at.minute == 0
    assert draft.needs_confirmation is False

    short_draft = parse_reminder_text(
        "проверить чай через 5 мин.",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert short_draft.intent_kind == "reminder"
    assert short_draft.reminder_text == "проверить чай"
    assert short_draft.due_at is not None
    assert short_draft.due_at.hour == 12
    assert short_draft.due_at.minute == 5
    assert short_draft.needs_confirmation is False


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


def test_parse_russian_day_after_tomorrow_without_time_needs_confirmation() -> None:
    draft = parse_reminder_text(
        "забрать заказ послезавтра",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "reminder"
    assert draft.reminder_text == "забрать заказ"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-26"
    assert draft.due_at.hour == 0
    assert draft.parse_confidence < 0.75
    assert draft.needs_confirmation is True


def test_parse_russian_day_part_defaults_confident() -> None:
    evening = parse_reminder_text(
        "созвониться сегодня вечером",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert evening.intent_kind == "reminder"
    assert evening.reminder_text == "созвониться"
    assert evening.due_at is not None
    assert evening.due_at.date().isoformat() == "2026-06-24"
    assert evening.due_at.hour == 19
    assert evening.due_at.minute == 0
    assert evening.needs_confirmation is False

    afternoon = parse_reminder_text(
        "забрать доставку завтра днем",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert afternoon.intent_kind == "reminder"
    assert afternoon.reminder_text == "забрать доставку"
    assert afternoon.due_at is not None
    assert afternoon.due_at.date().isoformat() == "2026-06-25"
    assert afternoon.due_at.hour == 13
    assert afternoon.needs_confirmation is False


def test_parse_russian_time_with_day_modifier_confident() -> None:
    draft = parse_reminder_text(
        "принять таблетку в 9 утра",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "reminder"
    assert draft.reminder_text == "принять таблетку"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-25"
    assert draft.due_at.hour == 9
    assert draft.due_at.minute == 0
    assert draft.needs_confirmation is False


def test_parse_russian_24_hour_time_confident() -> None:
    draft = parse_reminder_text(
        "позвонить маме в 21:30",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "reminder"
    assert draft.reminder_text == "позвонить маме"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-24"
    assert draft.due_at.hour == 21
    assert draft.due_at.minute == 30
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


def test_conflicting_temporal_phrase_needs_confirmation() -> None:
    draft = parse_reminder_text(
        "созвон завтра в 9 или в 10",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "reminder"
    assert draft.due_at is None
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
