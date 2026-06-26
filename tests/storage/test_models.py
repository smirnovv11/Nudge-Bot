from __future__ import annotations

from sqlalchemy import Enum

from nudge_bot.reminders.enums import (
    CallbackAction,
    CallbackEventStatus,
    DraftStatus,
    DraftType,
    ReminderDeliveryStatus,
    ReminderSourceType,
    ReminderStatus,
    ReminderType,
)
from nudge_bot.storage.models import CallbackEvent, Draft, Reminder, ReminderAttempt


def test_orm_enum_columns_match_postgresql_enum_names_and_values() -> None:
    expected = {
        Reminder.__table__.c.type: ("reminder_type", ReminderType),
        Reminder.__table__.c.status: ("reminder_status", ReminderStatus),
        Reminder.__table__.c.source_type: ("reminder_source_type", ReminderSourceType),
        ReminderAttempt.__table__.c.delivery_status: (
            "reminder_delivery_status",
            ReminderDeliveryStatus,
        ),
        Draft.__table__.c.type: ("draft_type", DraftType),
        Draft.__table__.c.status: ("draft_status", DraftStatus),
        CallbackEvent.__table__.c.action: ("callback_action", CallbackAction),
        CallbackEvent.__table__.c.status: ("callback_event_status", CallbackEventStatus),
    }

    for column, (type_name, enum_class) in expected.items():
        enum_type = column.type

        assert isinstance(enum_type, Enum)
        assert enum_type.name == type_name
        assert enum_type.enums == [member.value for member in enum_class]


def test_orm_models_define_documented_extra_indexes() -> None:
    expected = {
        Reminder: {
            "reminders_due_deliverable_idx",
            "reminders_sending_locked_idx",
            "reminders_user_status_due_idx",
            "reminders_user_completed_idx",
        },
        ReminderAttempt: {
            "reminder_attempts_reminder_attempt_uidx",
            "reminder_attempts_retry_idx",
        },
        Draft: {
            "drafts_user_pending_idx",
            "drafts_expiration_idx",
        },
        CallbackEvent: {
            "callback_events_reminder_created_idx",
            "callback_events_user_created_idx",
        },
    }

    for model, index_names in expected.items():
        assert index_names <= {index.name for index in model.__table__.indexes}
