from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nudge_bot.reminders.parser import parse_reminder_text


def test_parse_relative_reminder_confident() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=ZoneInfo("Europe/Minsk"))

    draft = parse_reminder_text(
        "walk the dog in 20 minutes",
        now=now,
        timezone="Europe/Minsk",
    )

    assert draft.intent_kind == "reminder"
    assert draft.due_at is not None
    assert draft.parse_confidence >= 0.75
    assert draft.needs_confirmation is False


def test_empty_text_needs_confirmation() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=ZoneInfo("Europe/Minsk"))

    draft = parse_reminder_text("", now=now, timezone="Europe/Minsk")

    assert draft.intent_kind == "unknown"
    assert draft.due_at is None
    assert draft.needs_confirmation is True
