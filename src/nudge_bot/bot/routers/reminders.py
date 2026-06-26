from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nudge_bot.bot.callbacks import ReminderDraftCallback
from nudge_bot.bot.keyboards import draft_confirmation_keyboard
from nudge_bot.config import Settings
from nudge_bot.reminders.services import DraftFlowService, TextReminderService
from nudge_bot.reminders.services.schemas import (
    DraftActionResult,
    TextReminderResult,
)
from nudge_bot.storage.unit_of_work import unit_of_work

router = Router(name="reminders")
draft_flow_service = DraftFlowService()
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
            unavailable_message = "I could not find your reminder draft."
        elif callback_data.action == "confirm":
            try:
                result = await draft_flow_service.confirm_draft(
                    uow,
                    draft_id=callback_data.draft_id,
                    user_id=user.id,
                    now=datetime.now(UTC),
                )
            except (LookupError, ValueError):
                unavailable_message = "This reminder draft is no longer available."
        else:
            try:
                result = await draft_flow_service.cancel_draft(
                    uow,
                    draft_id=callback_data.draft_id,
                    user_id=user.id,
                    now=datetime.now(UTC),
                )
            except LookupError:
                unavailable_message = "This reminder draft is no longer available."

    if unavailable_message is not None:
        await callback.answer(unavailable_message, show_alert=True)
        return

    await callback.answer()
    if result is not None and isinstance(callback.message, Message):
        await callback.message.edit_text(format_draft_action_result(result))


def format_text_reminder_result(result: TextReminderResult) -> str:
    if result.outcome == "created" and result.reminder is not None:
        return (
            "Reminder created.\n"
            f"Text: {result.reminder.reminder_text}\n"
            f"When: {_format_datetime(result.reminder.due_at, result.display_timezone)}"
        )

    if result.outcome == "draft" and result.draft is not None:
        return (
            "Create reminder?\n"
            f"Text: {result.draft.parsed_text}\n"
            f"When: {_format_datetime(result.draft.parsed_due_at, result.display_timezone)}"
        )

    if result.outcome == "note":
        return "Notes are not part of the MVP yet. Send a reminder with a time."

    return "I could not find a reminder time. Try something like: walk the dog in 20 minutes."


def format_draft_action_result(result: DraftActionResult) -> str:
    if result.outcome == "confirmed" and result.reminder is not None:
        due_at = _format_datetime(result.reminder.due_at, result.display_timezone)
        return f"Reminder created.\nText: {result.reminder.reminder_text}\nWhen: {due_at}"

    if result.outcome == "cancelled":
        return "Reminder draft cancelled."

    if result.outcome == "already_confirmed":
        return "This reminder draft was already confirmed."

    if result.outcome == "expired":
        return "This reminder draft expired. Send the reminder again."

    return "This reminder draft was already cancelled."


def _format_datetime(value: datetime | None, timezone: object = None) -> str:
    if value is None:
        return "unknown"
    if isinstance(timezone, str):
        try:
            value = value.astimezone(ZoneInfo(timezone))
        except ZoneInfoNotFoundError:
            value = value.astimezone(ZoneInfo("UTC"))
    return value.strftime("%Y-%m-%d %H:%M")
