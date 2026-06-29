from __future__ import annotations

from nudge_bot.config import Settings
from nudge_bot.constants import (
    DEFAULT_REPEAT_INTERVAL_MINUTES,
    DEFAULT_TIMEZONE,
    SCHEDULER_POLL_INTERVAL_SECONDS,
    VOICE_MAX_FILE_SIZE_MB,
    VOICE_TRANSCRIPTION_COMPUTE_TYPE,
    VOICE_TRANSCRIPTION_DEVICE,
    VOICE_TRANSCRIPTION_LANGUAGE,
    VOICE_TRANSCRIPTION_MODEL,
)


def test_settings_defaults_match_mvp() -> None:
    settings = Settings()

    assert settings.default_timezone == DEFAULT_TIMEZONE
    assert settings.default_repeat_interval_minutes == DEFAULT_REPEAT_INTERVAL_MINUTES
    assert settings.scheduler_poll_interval_seconds == SCHEDULER_POLL_INTERVAL_SECONDS
    assert settings.voice_transcription_model == VOICE_TRANSCRIPTION_MODEL
    assert settings.voice_transcription_compute_type == VOICE_TRANSCRIPTION_COMPUTE_TYPE
    assert settings.voice_transcription_device == VOICE_TRANSCRIPTION_DEVICE
    assert settings.voice_transcription_language == VOICE_TRANSCRIPTION_LANGUAGE
    assert settings.voice_max_file_size_mb == VOICE_MAX_FILE_SIZE_MB
