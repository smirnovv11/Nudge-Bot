from __future__ import annotations

import logging
from datetime import UTC, datetime
from io import BytesIO
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nudge_bot.bot.callbacks import ReminderActionCallback, ReminderDraftCallback
from nudge_bot.bot.keyboards import draft_confirmation_keyboard, edit_time_cancel_keyboard
from nudge_bot.config import Settings
from nudge_bot.reminders.domain import ReminderResult
from nudge_bot.reminders.enums import CallbackAction, DraftType, ReminderStatus
from nudge_bot.reminders.services import (
    DraftFlowService,
    ReminderActionService,
    ReminderEditTimeService,
    TextReminderService,
    VoiceReminderService,
)
from nudge_bot.reminders.services.schemas import (
    DraftActionOutcome,
    DraftActionResult,
    EditTimeOutcome,
    EditTimeResult,
    TextReminderOutcome,
    TextReminderResult,
    VoiceReminderOutcome,
    VoiceReminderResult,
)
from nudge_bot.reminders.services.voice import BYTES_PER_MEGABYTE
from nudge_bot.storage.unit_of_work import unit_of_work

router = Router(name="reminders")
logger = logging.getLogger(__name__)
draft_flow_service = DraftFlowService()
reminder_action_service = ReminderActionService()
reminder_edit_time_service = ReminderEditTimeService()
text_reminder_service = TextReminderService()
voice_reminder_service = VoiceReminderService()


class VoiceDownloadTooLargeError(Exception):
    pass


class LimitedBytesIO(BytesIO):
    def __init__(self, *, max_bytes: int) -> None:
        super().__init__()
        self._max_bytes = max_bytes

    def write(self, data: bytes) -> int:
        if self.tell() + len(data) > self._max_bytes:
            raise VoiceDownloadTooLargeError

        return super().write(data)


async def warm_up_voice_services(settings: Settings) -> None:
    try:
        await voice_reminder_service.warm_up(settings)
    except Exception:
        logger.warning("voice transcription warmup failed", exc_info=True)


@router.message(F.text)
async def handle_text_message(
    message: Message,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if message.from_user is None or message.text is None:
        return

    async with unit_of_work(session_factory) as uow:
        edit_time_result = await reminder_edit_time_service.apply_edit_time_text(
            uow,
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            locale=message.from_user.language_code,
            text=message.text,
            now=datetime.now(UTC),
            settings=settings,
        )
        if edit_time_result.outcome == EditTimeOutcome.NO_PENDING_DRAFT:
            result = await text_reminder_service.handle_text_reminder(
                uow,
                telegram_user_id=message.from_user.id,
                username=message.from_user.username,
                locale=message.from_user.language_code,
                text=message.text,
                now=datetime.now(UTC),
                settings=settings,
            )
        else:
            result = None

    if edit_time_result.outcome != EditTimeOutcome.NO_PENDING_DRAFT:
        await message.answer(format_edit_time_result(edit_time_result), parse_mode="HTML")
        return

    if result.outcome == TextReminderOutcome.DRAFT and result.draft is not None:
        await message.answer(
            format_text_reminder_result(result),
            reply_markup=draft_confirmation_keyboard(result.draft.id),
        )
        return

    await message.answer(format_text_reminder_result(result))


@router.message(F.voice | F.audio)
async def handle_voice_message(
    message: Message,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if message.from_user is None:
        return

    payload = voice_payload_from_message(message)
    if payload is None:
        await message.answer(
            format_voice_reminder_result(
                VoiceReminderResult(outcome=VoiceReminderOutcome.UNSUPPORTED)
            )
        )
        return

    file_size = payload["file_size"]
    validation_result = voice_reminder_service.validate_voice_input(
        file_size=file_size,
        duration_seconds=payload["duration"],
        settings=settings,
    )
    if validation_result is not None:
        await message.answer(format_voice_reminder_result(validation_result))
        return

    processing_message = await message.answer("Transcribing...")

    try:
        audio = await download_telegram_audio(
            bot,
            payload["file_id"],
            max_bytes=settings.voice_max_file_size_mb * BYTES_PER_MEGABYTE,
        )
    except VoiceDownloadTooLargeError:
        await edit_voice_processing_message(
            message=message,
            processing_message=processing_message,
            text=format_voice_reminder_result(
                VoiceReminderResult(outcome=VoiceReminderOutcome.TOO_LARGE),
            ),
        )
        return
    except TelegramBadRequest:
        logger.exception(
            "voice download failed",
            extra={"file_unique_id": payload["file_unique_id"]},
        )
        await edit_voice_processing_message(
            message=message,
            processing_message=processing_message,
            text=format_voice_reminder_result(
                VoiceReminderResult(outcome=VoiceReminderOutcome.TRANSCRIPTION_FAILED),
            ),
        )
        return

    validation_result = voice_reminder_service.validate_voice_input(
        audio=audio,
        file_size=file_size,
        duration_seconds=payload["duration"],
        settings=settings,
    )
    if validation_result is not None:
        await edit_voice_processing_message(
            message=message,
            processing_message=processing_message,
            text=format_voice_reminder_result(validation_result),
        )
        return

    async with unit_of_work(session_factory) as uow:
        pending_edit_result = await voice_reminder_service.reject_pending_edit_time(
            uow,
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            locale=message.from_user.language_code,
            now=datetime.now(UTC),
            settings=settings,
        )
    if pending_edit_result is not None:
        await edit_voice_processing_message(
            message=message,
            processing_message=processing_message,
            text=format_voice_reminder_result(pending_edit_result),
        )
        return

    transcription = await voice_reminder_service.transcribe_voice_audio(
        audio=audio,
        source_file_unique_id=payload["file_unique_id"],
        duration_seconds=payload["duration"],
        settings=settings,
    )

    async with unit_of_work(session_factory) as uow:
        result = await voice_reminder_service.process_voice_transcription(
            uow,
            telegram_user_id=message.from_user.id,
            username=message.from_user.username,
            locale=message.from_user.language_code,
            transcription=transcription,
            mime_type=payload["mime_type"],
            now=datetime.now(UTC),
            settings=settings,
        )

    if (
        result.text_result is not None
        and result.text_result.outcome == TextReminderOutcome.DRAFT
        and result.text_result.draft is not None
    ):
        await edit_voice_processing_message(
            message=message,
            processing_message=processing_message,
            text=format_voice_reminder_result(result),
            reply_markup=draft_confirmation_keyboard(result.text_result.draft.id),
        )
        return

    await edit_voice_processing_message(
        message=message,
        processing_message=processing_message,
        text=format_voice_reminder_result(result),
    )


@router.callback_query(
    ReminderDraftCallback.filter(
        F.action.in_({CallbackAction.CONFIRM.value, CallbackAction.CANCEL.value})
    )
)
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
        elif callback_data.action == CallbackAction.CONFIRM:
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
        if (
            callback_data.action == CallbackAction.CANCEL
            and result.draft.type == DraftType.REMINDER_EDIT_TIME
        ):
            try:
                await callback.message.delete()
            except TelegramBadRequest:
                logger.debug("edit-time prompt message was already unavailable")
            return

        await callback.message.edit_text(format_draft_action_result(result))


@router.callback_query(
    ReminderActionCallback.filter(
        F.action.in_(
            {
                CallbackAction.READ.value,
                CallbackAction.REPEAT.value,
                CallbackAction.CHOOSE_TIME.value,
            }
        )
    )
)
async def handle_reminder_action_callback(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    result: ReminderResult | None = None
    edit_time_result: EditTimeResult | None = None
    unavailable_message: str | None = None
    display_timezone: str | None = None
    callback_key = reminder_action_callback_key(callback_data, callback.id)

    try:
        async with unit_of_work(session_factory) as uow:
            user = await uow.users.get_by_telegram_id(callback.from_user.id)
            if user is None:
                unavailable_message = "🙈 I could not find this reminder"
            elif callback_data.action == CallbackAction.CHOOSE_TIME:
                display_timezone = (
                    user.settings.timezone
                    if user.settings is not None
                    else settings.default_timezone
                )
                edit_time_result = await reminder_edit_time_service.start_choose_time(
                    uow,
                    callback_key=callback_key,
                    reminder_id=callback_data.reminder_id,
                    user_id=user.id,
                    notification_id=callback_data.notification_id,
                    timezone=display_timezone,
                    now=datetime.now(UTC),
                )
            else:
                display_timezone = user.settings.timezone
                result = await reminder_action_service.process_callback_action(
                    uow,
                    callback_key=callback_key,
                    action=callback_data.action,
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

    if edit_time_result is not None:
        if should_send_edit_time_prompt(edit_time_result) and isinstance(callback.message, Message):
            await callback.answer()
            await callback.message.answer(
                format_edit_time_result(edit_time_result),
                reply_markup=edit_time_cancel_keyboard(edit_time_result.draft.id),
                parse_mode="HTML",
            )
            return

        if edit_time_result.outcome == EditTimeOutcome.AWAITING_INPUT:
            await callback.answer("Already waiting for a new time", show_alert=True)
            return

        await callback.answer(format_edit_time_result(edit_time_result), show_alert=True)
        return

    await callback.answer()
    if result is not None and isinstance(callback.message, Message):
        await callback.message.edit_text(format_reminder_action_result(result, display_timezone))


def format_text_reminder_result(result: TextReminderResult) -> str:
    if result.outcome == TextReminderOutcome.CREATED and result.reminder is not None:
        return (
            "✅ Reminder created\n\n"
            f"📝 {result.reminder.reminder_text}\n"
            f"🕒 {_format_datetime(result.reminder.due_at, result.display_timezone)}"
        )

    if result.outcome == TextReminderOutcome.DRAFT and result.draft is not None:
        return (
            "✨ Create this reminder?\n\n"
            f"📝 {result.draft.parsed_text}\n"
            f"🕒 {_format_datetime(result.draft.parsed_due_at, result.display_timezone)}"
        )

    if result.outcome == TextReminderOutcome.NOTE:
        return "🗒️ Notes are coming later\nSend a reminder with a time"

    return "🤔 I could not find a reminder time\nTry something like: walk the dog in 20 minutes"


def format_voice_reminder_result(result: VoiceReminderResult) -> str:
    if result.text_result is not None:
        return format_text_reminder_result(result.text_result)

    if result.outcome == VoiceReminderOutcome.PENDING_EDIT_TIME:
        return "Send the new time as text or press Cancel"

    if result.outcome == VoiceReminderOutcome.EMPTY_TRANSCRIPT:
        return "I could not hear a reminder in that voice message\nTry sending it as text"

    if result.outcome == VoiceReminderOutcome.TOO_LARGE:
        return "That audio is too large for voice reminders\nTry a shorter voice message"

    if result.outcome == VoiceReminderOutcome.TOO_LONG:
        return "That voice message is too long for fast reminders\nTry 15 seconds or less"

    if result.outcome == VoiceReminderOutcome.UNSUPPORTED:
        return "This audio message is not supported yet\nTry sending a Telegram voice message"

    return "Voice input is unavailable locally right now\nSend the reminder as text"


def format_draft_action_result(result: DraftActionResult) -> str:
    if result.outcome == DraftActionOutcome.CONFIRMED and result.reminder is not None:
        due_at = _format_datetime(result.reminder.due_at, result.display_timezone)
        return f"✅ Reminder created\n\n📝 {result.reminder.reminder_text}\n🕒 {due_at}"

    if result.outcome == DraftActionOutcome.CANCELLED:
        return "✖️ Reminder draft cancelled"

    if result.outcome == DraftActionOutcome.ALREADY_CONFIRMED:
        return "✅ This reminder draft was already confirmed"

    if result.outcome == DraftActionOutcome.EXPIRED:
        return "⌛ This reminder draft expired\nSend the reminder again"

    return "✖️ This reminder draft was already cancelled"


def format_reminder_action_result(
    result: ReminderResult,
    display_timezone: str | None = None,
) -> str:
    if result.status == ReminderStatus.COMPLETED:
        return "✅ Reminder completed"

    if result.status == ReminderStatus.SNOOZED:
        return f"🔁 Reminder repeated\n🕒 {_format_datetime(result.due_at, display_timezone)}"

    return "👌 Reminder already handled"


def format_edit_time_result(result: EditTimeResult) -> str:
    if result.outcome == EditTimeOutcome.AWAITING_INPUT:
        return (
            "🕒 Отправьте новое время\n"
            "Send the new time\n\n"
            "💡 <i>Например: завтра в 9 / через 20 минут</i>\n"
            "💡 <i>For example: tomorrow at 9 / in 20 minutes</i>"
        )

    if result.outcome == EditTimeOutcome.RESCHEDULED and result.reminder is not None:
        return (
            "✅ Reminder rescheduled\n"
            f"🕒 {_format_datetime(result.reminder.due_at, result.display_timezone)}"
        )

    if result.outcome == EditTimeOutcome.UNKNOWN:
        return "Не получилось понять новое время\nПопробуйте: завтра в 9 / через 20 минут"

    if result.outcome == EditTimeOutcome.EXPIRED:
        return "This time edit expired\nPress Choose time again"

    if result.outcome == EditTimeOutcome.ALREADY_HANDLED:
        return "This reminder is already handled"

    if result.outcome == EditTimeOutcome.CANCELLED:
        return "This time edit is no longer available"

    return "No reminder is waiting for a new time"


def should_send_edit_time_prompt(result: EditTimeResult) -> bool:
    return (
        result.outcome == EditTimeOutcome.AWAITING_INPUT
        and result.changed
        and result.draft is not None
    )


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


def voice_payload_from_message(message: Message) -> dict[str, object] | None:
    if message.voice is not None:
        return {
            "file_id": message.voice.file_id,
            "file_unique_id": message.voice.file_unique_id,
            "duration": message.voice.duration,
            "mime_type": message.voice.mime_type,
            "file_size": message.voice.file_size,
        }

    if message.audio is not None:
        return {
            "file_id": message.audio.file_id,
            "file_unique_id": message.audio.file_unique_id,
            "duration": message.audio.duration,
            "mime_type": message.audio.mime_type,
            "file_size": message.audio.file_size,
        }

    return None


async def download_telegram_audio(bot: Bot, file_id: object, *, max_bytes: int) -> bytes:
    buffer = LimitedBytesIO(max_bytes=max_bytes)
    await bot.download(file_id, destination=buffer)
    return buffer.getvalue()


async def edit_voice_processing_message(
    *,
    message: Message,
    processing_message: Message,
    text: str,
    reply_markup: object = None,
) -> None:
    try:
        await processing_message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await message.answer(text, reply_markup=reply_markup)
