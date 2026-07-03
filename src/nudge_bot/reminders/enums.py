from __future__ import annotations

from enum import StrEnum


class ReminderTypeEnum(StrEnum):
    ONE_OFF = "one_off"


class ReminderStatusEnum(StrEnum):
    ACTIVE = "active"
    SENDING = "sending"
    SENT = "sent"
    SNOOZED = "snoozed"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ReminderSourceTypeEnum(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    MANUAL = "manual"


class ParserIntentEnum(StrEnum):
    REMINDER = "reminder"
    NOTE = "note"
    UNKNOWN = "unknown"


class ReminderDeliveryStatusEnum(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    ABANDONED = "abandoned"


class DraftTypeEnum(StrEnum):
    REMINDER_CONFIRMATION = "reminder_confirmation"
    REMINDER_EDIT_TIME = "reminder_edit_time"
    REMINDER_EDIT_TEXT = "reminder_edit_text"
    NOTE_CAPTURE = "note_capture"


class DraftStatusEnum(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CallbackActionEnum(StrEnum):
    READ = "read"
    REPEAT = "repeat"
    CHOOSE_TIME = "choose_time"
    CONFIRM = "confirm"
    EDIT_TIME = "edit_time"
    EDIT_TEXT = "edit_text"
    CANCEL = "cancel"


class CallbackEventStatusEnum(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"
