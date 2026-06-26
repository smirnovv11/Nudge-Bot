from __future__ import annotations

from nudge_bot.common.constants import (
    DEFAULT_REPEAT_INTERVAL_MINUTES,
    DEFAULT_TIMEZONE,
    SCHEDULER_POLL_INTERVAL_SECONDS,
)
from nudge_bot.config import Settings


def test_settings_defaults_match_mvp() -> None:
    settings = Settings()

    assert settings.default_timezone == DEFAULT_TIMEZONE
    assert settings.default_repeat_interval_minutes == DEFAULT_REPEAT_INTERVAL_MINUTES
    assert settings.scheduler_poll_interval_seconds == SCHEDULER_POLL_INTERVAL_SECONDS
