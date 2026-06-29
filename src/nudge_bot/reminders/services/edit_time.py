from __future__ import annotations

from datetime import datetime, timedelta

from nudge_bot.common.constants import DRAFT_EXPIRATION_HOURS
from nudge_bot.config import Settings
from nudge_bot.reminders.draft_payloads import edit_time_payload, edit_time_reminder_id
from nudge_bot.reminders.enums import (
    CallbackAction,
    CallbackEventStatus,
    DraftStatus,
    DraftType,
    ReminderStatus,
)
from nudge_bot.reminders.parser import parse_reminder_text
from nudge_bot.reminders.services.schemas import EditTimeOutcome, EditTimeResult
from nudge_bot.reminders.services.time import (
    draft_display_timezone,
    is_expired,
    safe_timezone,
    to_utc,
)
from nudge_bot.storage.models import CallbackEvent, Draft
from nudge_bot.storage.unit_of_work import UnitOfWork

EDITABLE_REMINDER_STATUSES = {
    ReminderStatus.ACTIVE,
    ReminderStatus.SENT,
    ReminderStatus.SNOOZED,
}


class ReminderEditTimeService:
    async def start_choose_time(
        self,
        uow: UnitOfWork,
        *,
        callback_key: str,
        reminder_id: int,
        user_id: int,
        notification_id: int | None,
        timezone: str,
        now: datetime,
    ) -> EditTimeResult:
        now_utc = to_utc(now)
        user = await uow.users.get_by_id_for_update(user_id)
        if user is None:
            raise LookupError("user not found")

        existing_draft = await uow.drafts.get_pending_by_type_for_user_for_update(
            user_id=user_id,
            draft_type=DraftType.REMINDER_EDIT_TIME,
        )
        if existing_draft is not None:
            existing_result = await self._handle_existing_pending_draft(
                existing_draft,
                reminder_id=reminder_id,
                now_utc=now_utc,
                uow=uow,
            )
            if existing_result is not None:
                return existing_result

        reminder = await uow.reminders.get_by_id_for_user_for_update(
            reminder_id=reminder_id,
            user_id=user_id,
        )
        if reminder is None:
            raise LookupError("reminder not found")

        if reminder.status not in EDITABLE_REMINDER_STATUSES:
            return EditTimeResult(
                outcome=EditTimeOutcome.ALREADY_HANDLED,
                changed=False,
                display_timezone=timezone,
                reminder=reminder,
            )

        existing_event = await uow.callback_events.get_by_key(callback_key)
        if existing_event is None:
            event = CallbackEvent(
                user_id=user_id,
                reminder_id=reminder_id,
                callback_key=callback_key,
                action=CallbackAction.CHOOSE_TIME,
                status=CallbackEventStatus.RECEIVED,
            )
            uow.callback_events.add(event)
        else:
            event = existing_event

        draft = Draft(
            user_id=user_id,
            type=DraftType.REMINDER_EDIT_TIME,
            status=DraftStatus.PENDING,
            input_text="",
            parsed_text=None,
            parsed_due_at=None,
            parse_confidence=None,
            payload=edit_time_payload(
                reminder_id=reminder_id,
                notification_id=notification_id,
                callback_key=callback_key,
                timezone=timezone,
            ),
            expires_at=now_utc + timedelta(hours=DRAFT_EXPIRATION_HOURS),
        )
        uow.drafts.add(draft)
        event.status = CallbackEventStatus.PROCESSED
        event.processed_at = now_utc
        await uow.session.flush()

        return EditTimeResult(
            outcome=EditTimeOutcome.AWAITING_INPUT,
            changed=True,
            display_timezone=timezone,
            reminder=reminder,
            draft=draft,
        )

    async def apply_edit_time_text(
        self,
        uow: UnitOfWork,
        *,
        telegram_user_id: int,
        username: str | None,
        locale: str | None,
        text: str,
        now: datetime,
        settings: Settings,
    ) -> EditTimeResult:
        user = await uow.users.get_or_create(
            telegram_user_id=telegram_user_id,
            username=username,
            locale=locale,
            timezone=settings.default_timezone,
            repeat_interval_minutes=settings.default_repeat_interval_minutes,
        )
        requested_timezone = (
            user.settings.timezone if user.settings is not None else settings.default_timezone
        )
        timezone, zone = safe_timezone(requested_timezone, settings.default_timezone)
        now_utc = to_utc(now)
        draft = await uow.drafts.get_pending_by_type_for_user_for_update(
            user_id=user.id,
            draft_type=DraftType.REMINDER_EDIT_TIME,
        )
        if draft is None:
            return EditTimeResult(
                outcome=EditTimeOutcome.NO_PENDING_DRAFT,
                changed=False,
                display_timezone=timezone,
            )

        if is_expired(draft, now_utc):
            draft.status = DraftStatus.EXPIRED
            draft.updated_at = now_utc
            await uow.session.flush()
            return EditTimeResult(
                outcome=EditTimeOutcome.EXPIRED,
                changed=True,
                display_timezone=draft_display_timezone(draft) or timezone,
                draft=draft,
            )

        reminder_id = edit_time_reminder_id(draft)
        if reminder_id is None:
            draft.status = DraftStatus.CANCELLED
            draft.updated_at = now_utc
            await uow.session.flush()
            return EditTimeResult(
                outcome=EditTimeOutcome.CANCELLED,
                changed=True,
                display_timezone=draft_display_timezone(draft) or timezone,
                draft=draft,
            )

        reminder = await uow.reminders.get_by_id_for_user_for_update(
            reminder_id=reminder_id,
            user_id=user.id,
        )
        if reminder is None:
            raise LookupError("reminder not found")

        if reminder.status not in EDITABLE_REMINDER_STATUSES:
            draft.status = DraftStatus.CANCELLED
            draft.updated_at = now_utc
            await uow.session.flush()
            return EditTimeResult(
                outcome=EditTimeOutcome.ALREADY_HANDLED,
                changed=True,
                display_timezone=draft_display_timezone(draft) or timezone,
                reminder=reminder,
                draft=draft,
            )

        parsed = parse_reminder_text(text, now=now.astimezone(zone), timezone=timezone)
        if parsed.due_at is None or parsed.needs_confirmation:
            draft.input_text = text
            draft.parsed_text = parsed.reminder_text
            draft.parsed_due_at = to_utc(parsed.due_at) if parsed.due_at is not None else None
            draft.parse_confidence = parsed.parse_confidence
            draft.updated_at = now_utc
            await uow.session.flush()
            return EditTimeResult(
                outcome=EditTimeOutcome.UNKNOWN,
                changed=False,
                display_timezone=draft_display_timezone(draft) or timezone,
                reminder=reminder,
                draft=draft,
                parsed=parsed,
            )

        reminder.due_at = to_utc(parsed.due_at)
        reminder.status = ReminderStatus.SNOOZED
        reminder.locked_at = None
        draft.input_text = text
        draft.parsed_text = parsed.reminder_text
        draft.parsed_due_at = reminder.due_at
        draft.parse_confidence = parsed.parse_confidence
        draft.status = DraftStatus.CONFIRMED
        draft.updated_at = now_utc
        await uow.session.flush()

        return EditTimeResult(
            outcome=EditTimeOutcome.RESCHEDULED,
            changed=True,
            display_timezone=draft_display_timezone(draft) or timezone,
            reminder=reminder,
            draft=draft,
            parsed=parsed,
        )

    async def _handle_existing_pending_draft(
        self,
        draft: Draft,
        *,
        reminder_id: int,
        now_utc: datetime,
        uow: UnitOfWork,
    ) -> EditTimeResult | None:
        if is_expired(draft, now_utc):
            draft.status = DraftStatus.EXPIRED
            draft.updated_at = now_utc
            await uow.session.flush()
            return None

        if edit_time_reminder_id(draft) == reminder_id:
            return EditTimeResult(
                outcome=EditTimeOutcome.AWAITING_INPUT,
                changed=False,
                display_timezone=draft_display_timezone(draft),
                draft=draft,
            )

        draft.status = DraftStatus.CANCELLED
        draft.updated_at = now_utc
        await uow.session.flush()
        return None
