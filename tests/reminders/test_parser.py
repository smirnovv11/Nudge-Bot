from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nudge_bot.reminders.enums import ParserIntentEnum
from nudge_bot.reminders.parser import parse_reminder_text

NOW = datetime(2026, 6, 24, 12, 0, tzinfo=ZoneInfo("Europe/Minsk"))


def test_parse_relative_reminder_confident() -> None:
    draft = parse_reminder_text(
        "walk the dog in 20 minutes",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.REMINDER
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

    assert draft.intent_kind == ParserIntentEnum.REMINDER
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

    assert draft.intent_kind == ParserIntentEnum.REMINDER
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

    assert draft.intent_kind == ParserIntentEnum.REMINDER
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

    assert short_draft.intent_kind == ParserIntentEnum.REMINDER
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

    assert draft.intent_kind == ParserIntentEnum.REMINDER
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

    assert draft.intent_kind == ParserIntentEnum.REMINDER
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

    assert evening.intent_kind == ParserIntentEnum.REMINDER
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

    assert afternoon.intent_kind == ParserIntentEnum.REMINDER
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

    assert draft.intent_kind == ParserIntentEnum.REMINDER
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

    assert draft.intent_kind == ParserIntentEnum.REMINDER
    assert draft.reminder_text == "позвонить маме"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-24"
    assert draft.due_at.hour == 21
    assert draft.due_at.minute == 30
    assert draft.needs_confirmation is False


def test_parse_russian_time_with_space_separator_confident() -> None:
    draft = parse_reminder_text(
        "чай в 22 20",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.REMINDER
    assert draft.reminder_text == "чай"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-24"
    assert draft.due_at.hour == 22
    assert draft.due_at.minute == 20
    assert draft.needs_confirmation is False


def test_parse_russian_day_time_with_space_separator_confident() -> None:
    draft = parse_reminder_text(
        "чай завтра в 22 20",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.REMINDER
    assert draft.reminder_text == "чай"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-25"
    assert draft.due_at.hour == 22
    assert draft.due_at.minute == 20
    assert draft.needs_confirmation is False


def test_parse_russian_day_time_without_preposition_confident() -> None:
    cases = (
        ("цветы завтра 14:00", "2026-06-25", 14, 0),
        ("цветы завтра 14 00", "2026-06-25", 14, 0),
        ("цветы послезавтра 14:00", "2026-06-26", 14, 0),
        ("цветы сегодня 14 00", "2026-06-24", 14, 0),
    )

    for text, expected_date, expected_hour, expected_minute in cases:
        draft = parse_reminder_text(text, now=NOW, timezone="Europe/Minsk")

        assert draft.intent_kind == ParserIntentEnum.REMINDER
        assert draft.reminder_text == "цветы"
        assert draft.due_at is not None
        assert draft.due_at.date().isoformat() == expected_date
        assert draft.due_at.hour == expected_hour
        assert draft.due_at.minute == expected_minute
        assert draft.needs_confirmation is False


def test_parse_russian_weekday_with_full_and_short_names_confident() -> None:
    cases = (
        ("уведомление в понедельник 14:00", "2026-06-29", 14, 0),
        ("уведомление пн 14:00", "2026-06-29", 14, 0),
        ("уведомление во вторник 14:00", "2026-06-30", 14, 0),
        ("уведомление вт 14:00", "2026-06-30", 14, 0),
        ("уведомление в среду 14:00", "2026-06-24", 14, 0),
        ("уведомление ср 14:00", "2026-06-24", 14, 0),
        ("уведомление в четверг 14:00", "2026-06-25", 14, 0),
        ("уведомление чт 14:00", "2026-06-25", 14, 0),
        ("уведомление в пятницу 14:00", "2026-06-26", 14, 0),
        ("уведомление пт 14:00", "2026-06-26", 14, 0),
        ("уведомление в субботу 14:00", "2026-06-27", 14, 0),
        ("уведомление суббата 14:00", "2026-06-27", 14, 0),
        ("уведомление сб 14:00", "2026-06-27", 14, 0),
        ("уведомление в воскресенье 14:00", "2026-06-28", 14, 0),
        ("уведомление вс 14:00", "2026-06-28", 14, 0),
    )

    for text, expected_date, expected_hour, expected_minute in cases:
        draft = parse_reminder_text(text, now=NOW, timezone="Europe/Minsk")

        assert draft.intent_kind == ParserIntentEnum.REMINDER
        assert draft.reminder_text == "уведомление"
        assert draft.due_at is not None
        assert draft.due_at.date().isoformat() == expected_date
        assert draft.due_at.hour == expected_hour
        assert draft.due_at.minute == expected_minute
        assert draft.needs_confirmation is False


def test_parse_russian_weekday_hour_without_minutes_needs_confirmation() -> None:
    draft = parse_reminder_text(
        "пн 14 уведомление",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.REMINDER
    assert draft.reminder_text == "уведомление"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-29"
    assert draft.due_at.hour == 14
    assert draft.due_at.minute == 0
    assert draft.parse_confidence < 0.75
    assert draft.needs_confirmation is True


def test_parse_russian_weekday_alternatives_need_confirmation() -> None:
    cases = (
        "уведомление пн 14:00 или вт 15:00",
        "уведомление пн 14:00 и вт 15:00",
        "уведомление пн 14:00 или 15:00",
    )

    for text in cases:
        draft = parse_reminder_text(text, now=NOW, timezone="Europe/Minsk")

        assert draft.intent_kind == ParserIntentEnum.REMINDER
        assert draft.reminder_text == text
        assert draft.due_at is None
        assert draft.parse_confidence < 0.75
        assert draft.needs_confirmation is True


def test_parse_russian_same_weekday_past_time_rolls_to_next_week() -> None:
    future_today = parse_reminder_text(
        "уведомление ср 14:00",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert future_today.intent_kind == ParserIntentEnum.REMINDER
    assert future_today.reminder_text == "уведомление"
    assert future_today.due_at is not None
    assert future_today.due_at.date().isoformat() == "2026-06-24"
    assert future_today.due_at.hour == 14
    assert future_today.due_at.minute == 0
    assert future_today.needs_confirmation is False

    past_today = parse_reminder_text(
        "уведомление ср 9:00",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert past_today.intent_kind == ParserIntentEnum.REMINDER
    assert past_today.reminder_text == "уведомление"
    assert past_today.due_at is not None
    assert past_today.due_at.date().isoformat() == "2026-07-01"
    assert past_today.due_at.hour == 9
    assert past_today.due_at.minute == 0
    assert past_today.needs_confirmation is False


def test_parse_english_weekday_with_full_and_short_names_confident() -> None:
    cases = (
        ("notification on Monday 14:00", "2026-06-29", 14, 0),
        ("notification Mon 14:00", "2026-06-29", 14, 0),
        ("notification on Tuesday 14:00", "2026-06-30", 14, 0),
        ("notification Tue 14:00", "2026-06-30", 14, 0),
        ("notification on Wednesday 14:00", "2026-06-24", 14, 0),
        ("notification Wed 14:00", "2026-06-24", 14, 0),
        ("notification on Thursday 14:00", "2026-06-25", 14, 0),
        ("notification Thu 14:00", "2026-06-25", 14, 0),
        ("notification on Friday 14:00", "2026-06-26", 14, 0),
        ("notification Fri 14:00", "2026-06-26", 14, 0),
        ("notification on Saturday 14:00", "2026-06-27", 14, 0),
        ("notification Sat 14:00", "2026-06-27", 14, 0),
        ("notification on Sunday 14:00", "2026-06-28", 14, 0),
        ("notification Sun 14:00", "2026-06-28", 14, 0),
    )

    for text, expected_date, expected_hour, expected_minute in cases:
        draft = parse_reminder_text(text, now=NOW, timezone="Europe/Minsk")

        assert draft.intent_kind == ParserIntentEnum.REMINDER
        assert draft.reminder_text == "notification"
        assert draft.due_at is not None
        assert draft.due_at.date().isoformat() == expected_date
        assert draft.due_at.hour == expected_hour
        assert draft.due_at.minute == expected_minute
        assert draft.needs_confirmation is False


def test_parse_english_weekday_hour_without_minutes_needs_confirmation() -> None:
    draft = parse_reminder_text(
        "Mon 14 notification",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.REMINDER
    assert draft.reminder_text == "notification"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-29"
    assert draft.due_at.hour == 14
    assert draft.due_at.minute == 0
    assert draft.parse_confidence < 0.75
    assert draft.needs_confirmation is True


def test_parse_english_weekday_alternatives_need_confirmation() -> None:
    cases = (
        "notification Mon 14:00 or Tue 15:00",
        "notification Mon 14:00 and Tue 15:00",
        "notification Mon 14:00 or 15:00",
    )

    for text in cases:
        draft = parse_reminder_text(text, now=NOW, timezone="Europe/Minsk")

        assert draft.intent_kind == ParserIntentEnum.REMINDER
        assert draft.reminder_text == text
        assert draft.due_at is None
        assert draft.parse_confidence < 0.75
        assert draft.needs_confirmation is True


def test_parse_english_same_weekday_past_time_rolls_to_next_week() -> None:
    future_today = parse_reminder_text(
        "notification Wed 14:00",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert future_today.intent_kind == ParserIntentEnum.REMINDER
    assert future_today.reminder_text == "notification"
    assert future_today.due_at is not None
    assert future_today.due_at.date().isoformat() == "2026-06-24"
    assert future_today.due_at.hour == 14
    assert future_today.due_at.minute == 0
    assert future_today.needs_confirmation is False

    past_today = parse_reminder_text(
        "notification Wed 9:00",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert past_today.intent_kind == ParserIntentEnum.REMINDER
    assert past_today.reminder_text == "notification"
    assert past_today.due_at is not None
    assert past_today.due_at.date().isoformat() == "2026-07-01"
    assert past_today.due_at.hour == 9
    assert past_today.due_at.minute == 0
    assert past_today.needs_confirmation is False


def test_parse_english_weekday_with_ampm_confident() -> None:
    draft = parse_reminder_text(
        "notification Fri 2pm",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.REMINDER
    assert draft.reminder_text == "notification"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-26"
    assert draft.due_at.hour == 14
    assert draft.due_at.minute == 0
    assert draft.needs_confirmation is False


def test_parse_english_time_before_weekday_confident() -> None:
    draft = parse_reminder_text(
        "notification at 14:00 on Monday",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.REMINDER
    assert draft.reminder_text == "notification"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-29"
    assert draft.due_at.hour == 14
    assert draft.due_at.minute == 0
    assert draft.needs_confirmation is False


def test_parse_numeric_day_month_with_time_confident() -> None:
    cases = (
        ("цветы 30-06 14:00", "2026-06-30", 14, 0),
        ("цветы 30.06 14 00", "2026-06-30", 14, 0),
        ("цветы 30.06 в 14:00", "2026-06-30", 14, 0),
    )

    for text, expected_date, expected_hour, expected_minute in cases:
        draft = parse_reminder_text(text, now=NOW, timezone="Europe/Minsk")

        assert draft.intent_kind == ParserIntentEnum.REMINDER
        assert draft.reminder_text == "цветы"
        assert draft.due_at is not None
        assert draft.due_at.date().isoformat() == expected_date
        assert draft.due_at.hour == expected_hour
        assert draft.due_at.minute == expected_minute
        assert draft.needs_confirmation is False


def test_parse_numeric_day_month_without_time_needs_confirmation() -> None:
    draft = parse_reminder_text(
        "цветы 30.06",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.REMINDER
    assert draft.reminder_text == "цветы"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-30"
    assert draft.due_at.hour == 0
    assert draft.parse_confidence < 0.75
    assert draft.needs_confirmation is True


def test_plain_number_pair_without_time_marker_is_time() -> None:
    draft = parse_reminder_text(
        "ввв 22 30",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.REMINDER
    assert draft.reminder_text == "ввв"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-24"
    assert draft.due_at.hour == 22
    assert draft.due_at.minute == 30
    assert draft.needs_confirmation is False


def test_russian_text_number_pair_without_time_marker_is_time() -> None:
    draft = parse_reminder_text(
        "чай 21 22 30",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.REMINDER
    assert draft.reminder_text == "чай 21"
    assert draft.due_at is not None
    assert draft.due_at.date().isoformat() == "2026-06-24"
    assert draft.due_at.hour == 22
    assert draft.due_at.minute == 30
    assert draft.needs_confirmation is False


def test_parse_absolute_date_without_time_needs_confirmation() -> None:
    draft = parse_reminder_text(
        "забрать справку 26 февраля 2027 года",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.REMINDER
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

    assert draft.intent_kind == ParserIntentEnum.REMINDER
    assert draft.due_at is None
    assert draft.parse_confidence < 0.75
    assert draft.needs_confirmation is True


def test_explicit_note_marker_does_not_create_reminder() -> None:
    draft = parse_reminder_text(
        "заметка: забрать справку 26 февраля 2027 года",
        now=NOW,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == ParserIntentEnum.NOTE
    assert draft.reminder_text == "забрать справку 26 февраля 2027 года"
    assert draft.due_at is None
    assert draft.needs_confirmation is False


def test_unknown_text_needs_confirmation() -> None:
    draft = parse_reminder_text("купить молоко", now=NOW, timezone="Europe/Minsk")

    assert draft.intent_kind == ParserIntentEnum.UNKNOWN
    assert draft.reminder_text == "купить молоко"
    assert draft.due_at is None
    assert draft.needs_confirmation is True


def test_empty_text_needs_confirmation() -> None:
    draft = parse_reminder_text("", now=NOW, timezone="Europe/Minsk")

    assert draft.intent_kind == ParserIntentEnum.UNKNOWN
    assert draft.due_at is None
    assert draft.needs_confirmation is True
