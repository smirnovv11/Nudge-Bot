from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from nudge_bot.common.constants import DRAFT_EXPIRATION_HOURS
from nudge_bot.config import Settings
from nudge_bot.reminders.enums import (
    DraftStatusEnum,
    DraftTypeEnum,
    ParserIntentEnum,
    ReminderSourceTypeEnum,
    ReminderStatusEnum,
    ReminderTypeEnum,
)
from nudge_bot.reminders.parser import ParsedReminderDraft, parse_reminder_text
from nudge_bot.reminders.services.schemas import TextReminderOutcomeEnum, TextReminderResult
from nudge_bot.reminders.services.time import safe_timezone, to_utc
from nudge_bot.storage.models import Draft, Reminder
from nudge_bot.storage.unit_of_work import UnitOfWork

SOURCE_TYPE_PAYLOAD_KEY = "source_type"
SOURCE_METADATA_PAYLOAD_KEY = "source_metadata"
TIMEZONE_PAYLOAD_KEY = "timezone"


class ReminderIntakeService:
    async def handle_reminder_text(
        self,
        uow: UnitOfWork,
        *,
        telegram_user_id: int,
        username: str | None,
        locale: str | None,
        text: str,
        source_type: ReminderSourceTypeEnum,
        source_metadata: dict[str, Any] | None = None,
        now: datetime,
        settings: Settings,
    ) -> TextReminderResult:
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
        parsed = parse_reminder_text(text, now=now.astimezone(zone), timezone=timezone)
        metadata = dict(source_metadata or {})

        if parsed.intent_kind == ParserIntentEnum.NOTE:
            return TextReminderResult(
                outcome=TextReminderOutcomeEnum.NOTE,
                user_id=user.id,
                parsed=parsed,
                display_timezone=timezone,
            )

        if parsed.due_at is None or parsed.reminder_text is None:
            return TextReminderResult(
                outcome=TextReminderOutcomeEnum.UNKNOWN,
                user_id=user.id,
                parsed=parsed,
                display_timezone=timezone,
            )

        if parsed.needs_confirmation:
            draft = Draft(
                user_id=user.id,
                type=DraftTypeEnum.REMINDER_CONFIRMATION,
                status=DraftStatusEnum.PENDING,
                input_text=parsed.input_text,
                parsed_text=parsed.reminder_text,
                parsed_due_at=to_utc(parsed.due_at),
                parse_confidence=parsed.parse_confidence,
                payload={
                    TIMEZONE_PAYLOAD_KEY: timezone,
                    SOURCE_TYPE_PAYLOAD_KEY: source_type.value,
                    SOURCE_METADATA_PAYLOAD_KEY: metadata,
                },
                expires_at=now_utc + timedelta(hours=DRAFT_EXPIRATION_HOURS),
            )
            uow.drafts.add(draft)
            await uow.session.flush()
            return TextReminderResult(
                outcome=TextReminderOutcomeEnum.DRAFT,
                user_id=user.id,
                parsed=parsed,
                display_timezone=timezone,
                draft=draft,
            )

        reminder = reminder_from_parsed(
            user_id=user.id,
            parsed=parsed,
            source_type=source_type,
            source_metadata=metadata,
        )
        uow.reminders.add(reminder)
        await uow.session.flush()
        return TextReminderResult(
            outcome=TextReminderOutcomeEnum.CREATED,
            user_id=user.id,
            parsed=parsed,
            display_timezone=timezone,
            reminder=reminder,
        )


class TextReminderService:
    def __init__(self, intake_service: ReminderIntakeService | None = None) -> None:
        self._intake_service = intake_service or ReminderIntakeService()

    async def handle_text_reminder(
        self,
        uow: UnitOfWork,
        *,
        telegram_user_id: int,
        username: str | None,
        locale: str | None,
        text: str,
        now: datetime,
        settings: Settings,
    ) -> TextReminderResult:
        return await self._intake_service.handle_reminder_text(
            uow,
            telegram_user_id=telegram_user_id,
            username=username,
            locale=locale,
            text=text,
            source_type=ReminderSourceTypeEnum.TEXT,
            source_metadata={},
            now=now,
            settings=settings,
        )


def reminder_from_parsed(
    *,
    user_id: int,
    parsed: ParsedReminderDraft,
    source_type: ReminderSourceTypeEnum,
    source_metadata: dict[str, Any] | None = None,
) -> Reminder:
    if parsed.reminder_text is None or parsed.due_at is None:
        raise ValueError("parsed reminder must include reminder text and due time")

    return Reminder(
        user_id=user_id,
        type=ReminderTypeEnum.ONE_OFF,
        status=ReminderStatusEnum.ACTIVE,
        reminder_text=parsed.reminder_text,
        due_at=to_utc(parsed.due_at),
        source_type=source_type,
        extra=dict(source_metadata or {}),
    )
