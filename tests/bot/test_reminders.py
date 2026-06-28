from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nudge_bot.bot.callbacks import ReminderActionCallback, ReminderDraftCallback
from nudge_bot.bot.keyboards import (
    draft_confirmation_keyboard,
    edit_time_cancel_keyboard,
    reminder_actions_keyboard,
)
from nudge_bot.bot.routers.reminders import (
    format_draft_action_result,
    format_edit_time_result,
    format_reminder_action_result,
    format_text_reminder_result,
    reminder_action_callback_key,
    should_send_edit_time_prompt,
)
from nudge_bot.reminders.domain import ReminderResult
from nudge_bot.reminders.enums import DraftStatus, DraftType, ReminderStatus
from nudge_bot.reminders.parser import ParsedReminderDraft
from nudge_bot.reminders.services.schemas import (
    DraftActionResult,
    EditTimeResult,
    TextReminderResult,
)
from nudge_bot.storage.models import Draft, Reminder


def test_draft_confirmation_keyboard_packs_confirm_and_cancel_callbacks() -> None:
    keyboard = draft_confirmation_keyboard(draft_id=42)

    buttons = keyboard.inline_keyboard[0]
    callbacks = [ReminderDraftCallback.unpack(button.callback_data) for button in buttons]

    assert [button.text for button in buttons] == ["✅ Create", "✖️ Cancel"]
    assert callbacks == [
        ReminderDraftCallback(action="confirm", draft_id=42),
        ReminderDraftCallback(action="cancel", draft_id=42),
    ]


def test_edit_time_cancel_keyboard_packs_cancel_callback() -> None:
    keyboard = edit_time_cancel_keyboard(draft_id=42)

    button = keyboard.inline_keyboard[0][0]
    callback = ReminderDraftCallback.unpack(button.callback_data)

    assert button.text == "Cancel"
    assert callback == ReminderDraftCallback(action="cancel", draft_id=42)


def test_reminder_actions_keyboard_packs_fired_reminder_callbacks() -> None:
    keyboard = reminder_actions_keyboard(reminder_id=42, notification_id=7)

    buttons = keyboard.inline_keyboard[0]
    callbacks = [ReminderActionCallback.unpack(button.callback_data) for button in buttons]

    assert [button.text for button in buttons] == ["✅ Read", "🔁 Repeat", "🕒 Choose time"]
    assert callbacks == [
        ReminderActionCallback(action="read", reminder_id=42, notification_id=7),
        ReminderActionCallback(action="repeat", reminder_id=42, notification_id=7),
        ReminderActionCallback(action="choose_time", reminder_id=42, notification_id=7),
    ]


def test_text_result_format_for_created_reminder_is_user_facing() -> None:
    due_at = datetime(2026, 6, 24, 12, 20, tzinfo=UTC)
    result = TextReminderResult(
        outcome="created",
        user_id=10,
        parsed=ParsedReminderDraft(
            input_text="walk the dog in 20 minutes",
            reminder_text="walk the dog",
            due_at=due_at,
            parse_confidence=0.9,
            intent_kind="reminder",
            needs_confirmation=False,
        ),
        display_timezone="Europe/Minsk",
        reminder=Reminder(
            user_id=10,
            status=ReminderStatus.ACTIVE,
            reminder_text="walk the dog",
            due_at=due_at,
        ),
    )

    message = format_text_reminder_result(result)

    assert "✅ Reminder created" in message
    assert "walk the dog" in message
    assert "parse_confidence" not in message
    assert "metadata" not in message


def test_text_result_format_for_pending_draft_is_user_facing() -> None:
    due_at = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    result = TextReminderResult(
        outcome="draft",
        user_id=10,
        parsed=ParsedReminderDraft(
            input_text="pick up order tomorrow",
            reminder_text="pick up order",
            due_at=due_at,
            parse_confidence=0.6,
            intent_kind="reminder",
            needs_confirmation=True,
        ),
        display_timezone="Europe/Minsk",
        draft=Draft(
            id=42,
            user_id=10,
            type=DraftType.REMINDER_CONFIRMATION,
            status=DraftStatus.PENDING,
            input_text="pick up order tomorrow",
            parsed_text="pick up order",
            parsed_due_at=due_at,
            parse_confidence=0.6,
            payload={},
            expires_at=due_at + timedelta(hours=24),
        ),
    )

    message = format_text_reminder_result(result)

    assert "✨ Create this reminder?" in message
    assert "pick up order" in message
    assert "parse_confidence" not in message
    assert "payload" not in message


def test_draft_action_result_format_for_cancel_is_user_facing() -> None:
    draft = Draft(
        id=42,
        user_id=10,
        type=DraftType.REMINDER_CONFIRMATION,
        status=DraftStatus.CANCELLED,
        input_text="pick up order tomorrow",
        parsed_text="pick up order",
        parsed_due_at=datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
        parse_confidence=0.6,
        payload={},
        expires_at=datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
    )

    message = format_draft_action_result(
        DraftActionResult(outcome="cancelled", draft=draft, changed=True)
    )

    assert message == "✖️ Reminder draft cancelled"


def test_draft_action_result_format_for_expired_is_user_facing() -> None:
    draft = Draft(
        id=42,
        user_id=10,
        type=DraftType.REMINDER_CONFIRMATION,
        status=DraftStatus.EXPIRED,
        input_text="pick up order tomorrow",
        parsed_text="pick up order",
        parsed_due_at=datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
        parse_confidence=0.6,
        payload={},
        expires_at=datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
    )

    message = format_draft_action_result(
        DraftActionResult(outcome="expired", draft=draft, changed=False)
    )

    assert message == "⌛ This reminder draft expired\nSend the reminder again"


def test_draft_action_result_format_falls_back_for_invalid_timezone() -> None:
    due_at = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    reminder = Reminder(
        user_id=10,
        status=ReminderStatus.ACTIVE,
        reminder_text="pick up order",
        due_at=due_at,
    )

    message = format_draft_action_result(
        DraftActionResult(
            outcome="confirmed",
            draft=None,
            reminder=reminder,
            changed=True,
            display_timezone="Bad/Timezone",
        )
    )

    assert message == "✅ Reminder created\n\n📝 pick up order\n🕒 2026-06-25 12:00"


def test_reminder_action_result_format_is_user_facing() -> None:
    repeated_at = datetime(2026, 6, 25, 12, 5, tzinfo=UTC)

    assert (
        format_reminder_action_result(
            ReminderResult(
                reminder_id=42,
                status=ReminderStatus.SNOOZED,
                changed=True,
                due_at=repeated_at,
            )
        )
        == "🔁 Reminder repeated\n🕒 2026-06-25 12:05"
    )
    assert (
        format_reminder_action_result(
            ReminderResult(reminder_id=42, status=ReminderStatus.COMPLETED, changed=True)
        )
        == "✅ Reminder completed"
    )


def test_reminder_action_result_format_uses_display_timezone() -> None:
    repeated_at = datetime(2026, 6, 25, 21, 5, tzinfo=UTC)

    message = format_reminder_action_result(
        ReminderResult(
            reminder_id=42,
            status=ReminderStatus.SNOOZED,
            changed=True,
            due_at=repeated_at,
        ),
        "Europe/Minsk",
    )

    assert message == "🔁 Reminder repeated\n🕒 2026-06-26 00:05"


def test_edit_time_awaiting_input_format_is_user_facing() -> None:
    message = format_edit_time_result(
        EditTimeResult(
            outcome="awaiting_input",
            changed=True,
            display_timezone="Europe/Minsk",
        )
    )

    assert "Отправьте новое время" in message
    assert "через 20 минут" in message
    assert "payload" not in message
    assert "parse_confidence" not in message


def test_edit_time_prompt_is_sent_only_for_new_pending_draft() -> None:
    draft = Draft(
        id=42,
        user_id=10,
        type=DraftType.REMINDER_EDIT_TIME,
        status=DraftStatus.PENDING,
        input_text="",
        payload={"reminder_id": 1},
        expires_at=datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
    )

    assert (
        should_send_edit_time_prompt(
            EditTimeResult(outcome="awaiting_input", changed=True, draft=draft)
        )
        is True
    )
    assert (
        should_send_edit_time_prompt(
            EditTimeResult(outcome="awaiting_input", changed=False, draft=draft)
        )
        is False
    )


def test_edit_time_rescheduled_format_uses_display_timezone() -> None:
    reminder = Reminder(
        user_id=10,
        status=ReminderStatus.SNOOZED,
        reminder_text="pick up order",
        due_at=datetime(2026, 6, 25, 21, 5, tzinfo=UTC),
    )

    message = format_edit_time_result(
        EditTimeResult(
            outcome="rescheduled",
            changed=True,
            display_timezone="Europe/Minsk",
            reminder=reminder,
        )
    )

    assert message == "✅ Reminder rescheduled\n🕒 2026-06-26 00:05"


def test_reminder_action_callback_key_is_stable_for_notification() -> None:
    callback_data = ReminderActionCallback(
        action="repeat",
        reminder_id=42,
        notification_id=7,
    )

    assert (
        reminder_action_callback_key(callback_data, "telegram-callback-id")
        == "reminder:42:notification:7:action:repeat"
    )
