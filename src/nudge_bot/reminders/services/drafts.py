from __future__ import annotations

from datetime import datetime

from nudge_bot.reminders.enums import (
    DraftStatus,
    ReminderSourceType,
    ReminderStatus,
    ReminderType,
)
from nudge_bot.reminders.services.intake import SOURCE_METADATA_PAYLOAD_KEY, SOURCE_TYPE_PAYLOAD_KEY
from nudge_bot.reminders.services.schemas import DraftActionOutcome, DraftActionResult
from nudge_bot.reminders.services.time import draft_display_timezone, is_expired, to_utc
from nudge_bot.storage.models import Draft, Reminder
from nudge_bot.storage.unit_of_work import UnitOfWork


class DraftFlowService:
    async def confirm_draft(
        self,
        uow: UnitOfWork,
        *,
        draft_id: int,
        user_id: int,
        now: datetime,
    ) -> DraftActionResult:
        now_utc = to_utc(now)
        draft = await uow.drafts.get_by_id_for_user_for_update(
            draft_id=draft_id,
            user_id=user_id,
        )
        if draft is None:
            raise LookupError("draft not found")

        existing_result = await _inactive_draft_result(draft, now_utc, uow)
        if existing_result is not None:
            return existing_result

        if draft.parsed_text is None or draft.parsed_due_at is None:
            raise ValueError("draft cannot be confirmed without parsed reminder fields")

        display_timezone = draft_display_timezone(draft)
        if to_utc(draft.parsed_due_at) <= now_utc:
            draft.status = DraftStatus.EXPIRED
            draft.updated_at = now_utc
            await uow.session.flush()
            return DraftActionResult(
                outcome=DraftActionOutcome.EXPIRED,
                draft=draft,
                changed=True,
                display_timezone=display_timezone,
            )

        source_type = _draft_source_type(draft)
        source_metadata = _draft_source_metadata(draft)
        reminder = Reminder(
            user_id=user_id,
            type=ReminderType.ONE_OFF,
            status=ReminderStatus.ACTIVE,
            reminder_text=draft.parsed_text,
            due_at=draft.parsed_due_at,
            source_type=source_type,
            extra=source_metadata,
        )
        uow.reminders.add(reminder)
        draft.status = DraftStatus.CONFIRMED
        draft.updated_at = now_utc
        await uow.session.flush()

        return DraftActionResult(
            outcome=DraftActionOutcome.CONFIRMED,
            draft=draft,
            changed=True,
            display_timezone=display_timezone,
            reminder=reminder,
        )

    async def cancel_draft(
        self,
        uow: UnitOfWork,
        *,
        draft_id: int,
        user_id: int,
        now: datetime,
    ) -> DraftActionResult:
        now_utc = to_utc(now)
        draft = await uow.drafts.get_by_id_for_user_for_update(
            draft_id=draft_id,
            user_id=user_id,
        )
        if draft is None:
            raise LookupError("draft not found")

        existing_result = await _inactive_draft_result(draft, now_utc, uow)
        if existing_result is not None:
            return existing_result

        draft.status = DraftStatus.CANCELLED
        draft.updated_at = now_utc
        await uow.session.flush()

        return DraftActionResult(
            outcome=DraftActionOutcome.CANCELLED,
            draft=draft,
            changed=True,
            display_timezone=draft_display_timezone(draft),
        )


async def _inactive_draft_result(
    draft: Draft,
    now_utc: datetime,
    uow: UnitOfWork,
) -> DraftActionResult | None:
    display_timezone = draft_display_timezone(draft)

    if draft.status == DraftStatus.CONFIRMED:
        return DraftActionResult(
            outcome=DraftActionOutcome.ALREADY_CONFIRMED,
            draft=draft,
            changed=False,
            display_timezone=display_timezone,
        )
    if draft.status == DraftStatus.CANCELLED:
        return DraftActionResult(
            outcome=DraftActionOutcome.ALREADY_CANCELLED,
            draft=draft,
            changed=False,
            display_timezone=display_timezone,
        )
    if draft.status == DraftStatus.EXPIRED:
        return DraftActionResult(
            outcome=DraftActionOutcome.EXPIRED,
            draft=draft,
            changed=False,
            display_timezone=display_timezone,
        )
    if is_expired(draft, now_utc):
        draft.status = DraftStatus.EXPIRED
        draft.updated_at = now_utc
        await uow.session.flush()
        return DraftActionResult(
            outcome=DraftActionOutcome.EXPIRED,
            draft=draft,
            changed=True,
            display_timezone=display_timezone,
        )

    return None


def _draft_source_type(draft: Draft) -> ReminderSourceType:
    raw_source_type = draft.payload.get(SOURCE_TYPE_PAYLOAD_KEY)
    if isinstance(raw_source_type, str):
        try:
            return ReminderSourceType(raw_source_type)
        except ValueError:
            return ReminderSourceType.TEXT
    return ReminderSourceType.TEXT


def _draft_source_metadata(draft: Draft) -> dict[str, object]:
    raw_metadata = draft.payload.get(SOURCE_METADATA_PAYLOAD_KEY)
    return raw_metadata if isinstance(raw_metadata, dict) else {}
