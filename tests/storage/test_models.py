from __future__ import annotations

from sqlalchemy import Enum

from nudge_bot.reminders.enums import (
    CallbackActionEnum,
    CallbackEventStatusEnum,
    DraftStatusEnum,
    DraftTypeEnum,
    ReminderDeliveryStatusEnum,
    ReminderSourceTypeEnum,
    ReminderStatusEnum,
    ReminderTypeEnum,
)
from nudge_bot.storage.models import CallbackEvent, Draft, Reminder, ReminderAttempt


def test_orm_enum_columns_match_postgresql_enum_names_and_values() -> None:
    expected = {
        Reminder.__table__.c.type: ("reminder_type", ReminderTypeEnum),
        Reminder.__table__.c.status: ("reminder_status", ReminderStatusEnum),
        Reminder.__table__.c.source_type: ("reminder_source_type", ReminderSourceTypeEnum),
        ReminderAttempt.__table__.c.delivery_status: (
            "reminder_delivery_status",
            ReminderDeliveryStatusEnum,
        ),
        Draft.__table__.c.type: ("draft_type", DraftTypeEnum),
        Draft.__table__.c.status: ("draft_status", DraftStatusEnum),
        CallbackEvent.__table__.c.action: ("callback_action", CallbackActionEnum),
        CallbackEvent.__table__.c.status: ("callback_event_status", CallbackEventStatusEnum),
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
            "drafts_user_pending_edit_time_uidx",
        },
        CallbackEvent: {
            "callback_events_reminder_created_idx",
            "callback_events_user_created_idx",
        },
    }

    for model, index_names in expected.items():
        assert index_names <= {index.name for index in model.__table__.indexes}


def test_due_deliverable_index_includes_sent_for_auto_repeat() -> None:
    due_index = next(
        index
        for index in Reminder.__table__.indexes
        if index.name == "reminders_due_deliverable_idx"
    )
    predicate = str(due_index.dialect_options["postgresql"]["where"])

    assert "status IN ('active', 'snoozed', 'sent')" in predicate


def test_pending_edit_time_draft_index_is_unique() -> None:
    index = next(
        index
        for index in Draft.__table__.indexes
        if index.name == "drafts_user_pending_edit_time_uidx"
    )
    predicate = str(index.dialect_options["postgresql"]["where"])

    assert index.unique is True
    assert "status = 'pending'" in predicate
    assert "type = 'reminder_edit_time'" in predicate


def test_callback_events_has_timestamp_mixin_columns() -> None:
    assert "created_at" in CallbackEvent.__table__.c
    assert "updated_at" in CallbackEvent.__table__.c
