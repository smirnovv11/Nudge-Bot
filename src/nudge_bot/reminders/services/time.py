from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from nudge_bot.storage.models import Draft


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def safe_timezone(requested_timezone: str, default_timezone: str) -> tuple[str, ZoneInfo]:
    for timezone in (requested_timezone, default_timezone, "UTC"):
        try:
            return timezone, ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            continue
    return "UTC", ZoneInfo("UTC")


def draft_display_timezone(draft: Draft) -> str | None:
    timezone = draft.payload.get("timezone")
    return timezone if isinstance(timezone, str) else None


def is_expired(draft: Draft, now: datetime) -> bool:
    return to_utc(draft.expires_at) <= now
