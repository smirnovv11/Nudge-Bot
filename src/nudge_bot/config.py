from __future__ import annotations

from functools import lru_cache

from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

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


class Settings(BaseSettings):
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    database_url: str = Field(
        default="postgresql+asyncpg://nudge:nudge@localhost:5432/nudge",
        alias="DATABASE_URL",
    )
    default_timezone: str = Field(default=DEFAULT_TIMEZONE, alias="DEFAULT_TIMEZONE")
    default_repeat_interval_minutes: PositiveInt = Field(
        default=DEFAULT_REPEAT_INTERVAL_MINUTES,
        alias="DEFAULT_REPEAT_INTERVAL_MINUTES",
    )
    scheduler_poll_interval_seconds: PositiveInt = Field(
        default=SCHEDULER_POLL_INTERVAL_SECONDS,
        alias="SCHEDULER_POLL_INTERVAL_SECONDS",
    )
    voice_transcription_model: str = Field(
        default=VOICE_TRANSCRIPTION_MODEL,
        alias="VOICE_TRANSCRIPTION_MODEL",
    )
    voice_transcription_compute_type: str = Field(
        default=VOICE_TRANSCRIPTION_COMPUTE_TYPE,
        alias="VOICE_TRANSCRIPTION_COMPUTE_TYPE",
    )
    voice_transcription_device: str = Field(
        default=VOICE_TRANSCRIPTION_DEVICE,
        alias="VOICE_TRANSCRIPTION_DEVICE",
    )
    voice_transcription_language: str = Field(
        default=VOICE_TRANSCRIPTION_LANGUAGE,
        alias="VOICE_TRANSCRIPTION_LANGUAGE",
    )
    voice_max_file_size_mb: PositiveInt = Field(
        default=VOICE_MAX_FILE_SIZE_MB,
        alias="VOICE_MAX_FILE_SIZE_MB",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
