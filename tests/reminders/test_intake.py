from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nudge_bot.reminders.intake import TextReminderInput, TextReminderInputStrategy


def test_text_input_strategy_reuses_reminder_parser() -> None:
    strategy = TextReminderInputStrategy()

    draft = strategy.parse(
        TextReminderInput(
            text="walk the dog in 20 minutes",
            now=datetime(2026, 6, 24, 12, 0, tzinfo=ZoneInfo("Europe/Minsk")),
            timezone="Europe/Minsk",
        )
    )

    assert draft.intent_kind == "reminder"
    assert draft.due_at is not None
