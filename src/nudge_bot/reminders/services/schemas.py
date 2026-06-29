from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from nudge_bot.reminders.parser import ParsedReminderDraft
from nudge_bot.storage.models import Draft, Reminder


class TextReminderOutcome(StrEnum):
    CREATED = "created"
    DRAFT = "draft"
    UNKNOWN = "unknown"
    NOTE = "note"


class DraftActionOutcome(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    ALREADY_CONFIRMED = "already_confirmed"
    ALREADY_CANCELLED = "already_cancelled"
    EXPIRED = "expired"


class EditTimeOutcome(StrEnum):
    AWAITING_INPUT = "awaiting_input"
    RESCHEDULED = "rescheduled"
    UNKNOWN = "unknown"
    EXPIRED = "expired"
    ALREADY_HANDLED = "already_handled"
    CANCELLED = "cancelled"
    NO_PENDING_DRAFT = "no_pending_draft"


class VoiceTranscriptionOutcome(StrEnum):
    TRANSCRIBED = "transcribed"
    EMPTY = "empty"
    FAILED = "failed"
    TOO_LARGE = "too_large"
    UNSUPPORTED = "unsupported"


class VoiceReminderOutcome(StrEnum):
    PROCESSED = "processed"
    EMPTY_TRANSCRIPT = "empty_transcript"
    TRANSCRIPTION_FAILED = "transcription_failed"
    TOO_LARGE = "too_large"
    UNSUPPORTED = "unsupported"
    PENDING_EDIT_TIME = "pending_edit_time"


@dataclass(frozen=True)
class TextReminderResult:
    outcome: TextReminderOutcome
    user_id: int
    parsed: ParsedReminderDraft
    display_timezone: str
    reminder: Reminder | None = None
    draft: Draft | None = None


@dataclass(frozen=True)
class DraftActionResult:
    outcome: DraftActionOutcome
    draft: Draft
    changed: bool
    display_timezone: str | None = None
    reminder: Reminder | None = None


@dataclass(frozen=True)
class EditTimeResult:
    outcome: EditTimeOutcome
    changed: bool
    display_timezone: str | None = None
    reminder: Reminder | None = None
    draft: Draft | None = None
    parsed: ParsedReminderDraft | None = None


@dataclass(frozen=True)
class VoiceTranscript:
    text: str
    language: str | None
    duration_seconds: int | None
    model: str
    source_file_unique_id: str


@dataclass(frozen=True)
class VoiceTranscriptionResult:
    outcome: VoiceTranscriptionOutcome
    transcript: VoiceTranscript | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class VoiceReminderResult:
    outcome: VoiceReminderOutcome
    text_result: TextReminderResult | None = None
    error_message: str | None = None
