from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nudge_bot.bot.callbacks import ReminderActionCallback, ReminderDraftCallback
from nudge_bot.bot.keyboards import draft_confirmation_keyboard
from nudge_bot.config import Settings
from nudge_bot.reminders.domain import ReminderResult
from nudge_bot.reminders.enums import CallbackAction
from nudge_bot.reminders.services import (
    DraftFlowService,
    ReminderActionService,
    TextReminderService,
)
from nudge_bot.reminders.services.schemas import (
    DraftActionResult,
    TextReminderResult,
)
from nudge_bot.storage.unit_of_work import unit_of_work

router = Router(name="reminders")
logger = logging.getLogger(__name__)
draft_flow_service = DraftFlowService()
reminder_action_service = ReminderActionService()
text_reminder_service = TextReminderService()


@router.message(F.text)
async def handle_text_message(
    message: Message,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if message.from_user is None or message.text is None:
        return

    async with unit_of_work(session_factory) as uow:
        result = await text_reminder_service.handle_text_reminder(
            uow,
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            locale=message.from_user.language_code,
            text=message.text,
            now=datetime.now(UTC),
            settings=settings,
        )

    if result.outcome == "draft" and result.draft is not None:
        await message.answer(
            format_text_reminder_result(result),
            reply_markup=draft_confirmation_keyboard(result.draft.id),
        )
        return

    await message.answer(format_text_reminder_result(result))


@router.callback_query(ReminderDraftCallback.filter(F.action.in_({"confirm", "cancel"})))
async def handle_draft_callback(
    callback: CallbackQuery,
    callback_data: ReminderDraftCallback,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    result: DraftActionResult | None = None
    unavailable_message: str | None = None

    async with unit_of_work(session_factory) as uow:
        user = await uow.users.get_by_telegram_id(callback.from_user.id)
        if user is None:
            unavailable_message = "🙈 I could not find your reminder draft"
        elif callback_data.action == "confirm":
            try:
                result = await draft_flow_service.confirm_draft(
                    uow,
                    draft_id=callback_data.draft_id,
                    user_id=user.id,
                    now=datetime.now(UTC),
                )
            except (LookupError, ValueError):
                unavailable_message = "🙈 This reminder draft is no longer available"
        else:
            try:
                result = await draft_flow_service.cancel_draft(
                    uow,
                    draft_id=callback_data.draft_id,
                    user_id=user.id,
                    now=datetime.now(UTC),
                )
            except LookupError:
                unavailable_message = "🙈 This reminder draft is no longer available"

    if unavailable_message is not None:
        await callback.answer(unavailable_message, show_alert=True)
        return

    await callback.answer()
    if result is not None and isinstance(callback.message, Message):
        await callback.message.edit_text(format_draft_action_result(result))


@router.callback_query(
    ReminderActionCallback.filter(F.action.in_({"read", "repeat", "choose_time"}))
)
async def handle_reminder_action_callback(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if callback_data.action == "choose_time":
        await callback.answer("🕒 Choosing a custom time is coming soon", show_alert=True)
        return

    result: ReminderResult | None = None
    unavailable_message: str | None = None
    display_timezone: str | None = None
    callback_key = reminder_action_callback_key(callback_data, callback.id)

    try:
        async with unit_of_work(session_factory) as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)
            if user is None:
                unavailable_message = "🙈 I could not find this reminder"
            else:
                display_timezone = user.settings.timezone
                result = await reminder_action_service.process_callback_action(
                    uow,
                    callback_key=callback_key,
                    action=CallbackAction(callback_data.action),
                    reminder_id=callback_data.reminder_id,
                    user_id=user.id,
                    interval_minutes=user.settings.repeat_interval_minutes,
                    now=datetime.now(UTC),
                )
    except LookupError:
        unavailable_message = "🙈 This reminder is no longer available"
    except Exception:
        logger.exception(
            "reminder action callback failed",
            extra={
                "reminder_id": callback_data.reminder_id,
                "action": callback_data.action,
            },
        )
        await callback.answer("⚠️ Could not process this action\nPlease try again", show_alert=True)
        return

    if unavailable_message is not None:
        await callback.answer(unavailable_message, show_alert=True)
        return

    await callback.answer()
    if result is not None and isinstance(callback.message, Message):
        await callback.message.edit_text(format_reminder_action_result(result, display_timezone))


def format_text_reminder_result(result: TextReminderResult) -> str:
    if result.outcome == "created" and result.reminder is not None:
        return (
            "✅ Reminder created\n\n"
            f"📝 {result.reminder.reminder_text}\n"
            f"🕒 {_format_datetime(result.reminder.due_at, result.display_timezone)}"
        )

    if result.outcome == "draft" and result.draft is not None:
        return (
            "✨ Create this reminder?\n\n"
            f"📝 {result.draft.parsed_text}\n"
            f"🕒 {_format_datetime(result.draft.parsed_due_at, result.display_timezone)}"
        )

    if result.outcome == "note":
        return "🗒️ Notes are coming later\nSend a reminder with a time"

    return "🤔 I could not find a reminder time\nTry something like: walk the dog in 20 minutes"


def format_draft_action_result(result: DraftActionResult) -> str:
    if result.outcome == "confirmed" and result.reminder is not None:
        due_at = _format_datetime(result.reminder.due_at, result.display_timezone)
        return f"✅ Reminder created\n\n📝 {result.reminder.reminder_text}\n🕒 {due_at}"

    if result.outcome == "cancelled":
        return "✖️ Reminder draft cancelled"

    if result.outcome == "already_confirmed":
        return "✅ This reminder draft was already confirmed"

    if result.outcome == "expired":
        return "⌛ This reminder draft expired\nSend the reminder again"

    return "✖️ This reminder draft was already cancelled"


def format_reminder_action_result(
    result: ReminderResult,
    display_timezone: str | None = None,
) -> str:
    if result.status.value == "completed":
        return "✅ Reminder completed"

    if result.status.value == "snoozed":
        return f"🔁 Reminder repeated\n🕒 {_format_datetime(result.due_at, display_timezone)}"

    return "👌 Reminder already handled"


def reminder_action_callback_key(
    callback_data: ReminderActionCallback,
    callback_id: str,
) -> str:
    if callback_data.notification_id is None:
        return f"telegram-callback:{callback_id}"
    return (
        f"reminder:{callback_data.reminder_id}:"
        f"notification:{callback_data.notification_id}:"
        f"action:{callback_data.action}"
    )


def _format_datetime(value: datetime | None, timezone: object = None) -> str:
    if value is None:
        return "unknown"
    if isinstance(timezone, str):
        try:
            value = value.astimezone(ZoneInfo(timezone))
        except ZoneInfoNotFoundError:
            value = value.astimezone(ZoneInfo("UTC"))
    return value.strftime("%Y-%m-%d %H:%M")
