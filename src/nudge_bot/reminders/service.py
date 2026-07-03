from __future__ import annotations

from datetime import datetime

from nudge_bot.config import Settings
from nudge_bot.reminders.domain import ReminderResult, ReminderToSend
from nudge_bot.reminders.enums import CallbackActionEnum
from nudge_bot.reminders.services import (
    DraftActionResult,
    DraftFlowService,
    EditTimeResult,
    ReminderActionService,
    ReminderEditTimeService,
    ReminderSchedulerService,
    TextReminderResult,
    TextReminderService,
)
from nudge_bot.storage.unit_of_work import UnitOfWork

_draft_flow_service = DraftFlowService()
_reminder_action_service = ReminderActionService()
_reminder_edit_time_service = ReminderEditTimeService()
_reminder_scheduler_service = ReminderSchedulerService()
_text_reminder_service = TextReminderService()


async def claim_due_reminders(
    uow: UnitOfWork,
    *,
    limit: int,
    now: datetime,
) -> list[ReminderToSend]:
    return await _reminder_scheduler_service.claim_due_reminders(uow, limit=limit, now=now)


async def handle_text_reminder(
    uow: UnitOfWork,
    *,
    telegram_user_id: int,
    username: str | None,
    locale: str | None,
    text: str,
    now: datetime,
    settings: Settings,
) -> TextReminderResult:
    return await _text_reminder_service.handle_text_reminder(
        uow,
        telegram_user_id=telegram_user_id,
        username=username,
        locale=locale,
        text=text,
        now=now,
        settings=settings,
    )


async def confirm_draft(
    uow: UnitOfWork,
    *,
    draft_id: int,
    user_id: int,
    now: datetime,
) -> DraftActionResult:
    return await _draft_flow_service.confirm_draft(
        uow,
        draft_id=draft_id,
        user_id=user_id,
        now=now,
    )


async def cancel_draft(
    uow: UnitOfWork,
    *,
    draft_id: int,
    user_id: int,
    now: datetime,
) -> DraftActionResult:
    return await _draft_flow_service.cancel_draft(
        uow,
        draft_id=draft_id,
        user_id=user_id,
        now=now,
    )


async def mark_completed(
    uow: UnitOfWork,
    *,
    reminder_id: int,
    user_id: int,
    now: datetime | None = None,
) -> ReminderResult:
    return await _reminder_action_service.mark_completed(
        uow,
        reminder_id=reminder_id,
        user_id=user_id,
        now=now,
    )


async def snooze(
    uow: UnitOfWork,
    *,
    reminder_id: int,
    user_id: int,
    interval_minutes: int,
    now: datetime | None = None,
) -> ReminderResult:
    return await _reminder_action_service.snooze(
        uow,
        reminder_id=reminder_id,
        user_id=user_id,
        interval_minutes=interval_minutes,
        now=now,
    )


async def process_callback_action(
    uow: UnitOfWork,
    *,
    callback_key: str,
    action: CallbackActionEnum,
    reminder_id: int,
    user_id: int,
    interval_minutes: int,
    now: datetime | None = None,
) -> ReminderResult:
    return await _reminder_action_service.process_callback_action(
        uow,
        callback_key=callback_key,
        action=action,
        reminder_id=reminder_id,
        user_id=user_id,
        interval_minutes=interval_minutes,
        now=now,
    )


async def start_choose_time(
    uow: UnitOfWork,
    *,
    callback_key: str,
    reminder_id: int,
    user_id: int,
    notification_id: int | None,
    timezone: str,
    now: datetime,
) -> EditTimeResult:
    return await _reminder_edit_time_service.start_choose_time(
        uow,
        callback_key=callback_key,
        reminder_id=reminder_id,
        user_id=user_id,
        notification_id=notification_id,
        timezone=timezone,
        now=now,
    )


async def apply_edit_time_text(
    uow: UnitOfWork,
    *,
    telegram_user_id: int,
    username: str | None,
    locale: str | None,
    text: str,
    now: datetime,
    settings: Settings,
) -> EditTimeResult:
    return await _reminder_edit_time_service.apply_edit_time_text(
        uow,
        telegram_user_id=telegram_user_id,
        username=username,
        locale=locale,
        text=text,
        now=now,
        settings=settings,
    )
