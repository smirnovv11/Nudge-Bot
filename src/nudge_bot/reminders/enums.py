from __future__ import annotations

from enum import StrEnum


class ReminderType(StrEnum):
    ONE_OFF = "one_off"


class ReminderStatus(StrEnum):
    ACTIVE = "active"
    SENDING = "sending"
    SENT = "sent"
    SNOOZED = "snoozed"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ReminderSourceType(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    MANUAL = "manual"


class ReminderDeliveryStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    ABANDONED = "abandoned"


class DraftType(StrEnum):
    REMINDER_CONFIRMATION = "reminder_confirmation"
    REMINDER_EDIT_TIME = "reminder_edit_time"
    REMINDER_EDIT_TEXT = "reminder_edit_text"
    NOTE_CAPTURE = "note_capture"


class DraftStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CallbackAction(StrEnum):
    READ = "read"
    REPEAT = "repeat"
    CHOOSE_TIME = "choose_time"
    CONFIRM = "confirm"
    EDIT_TIME = "edit_time"
    EDIT_TEXT = "edit_text"
    CANCEL = "cancel"


class CallbackEventStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"
