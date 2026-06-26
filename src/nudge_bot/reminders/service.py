from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from nudge_bot.common.constants import DRAFT_EXPIRATION_HOURS
from nudge_bot.config import Settings
from nudge_bot.reminders.domain import ReminderResult, ReminderToSend
from nudge_bot.reminders.enums import (
    DraftStatus,
    DraftType,
    ReminderSourceType,
    ReminderStatus,
    ReminderType,
)
from nudge_bot.reminders.parser import ParsedReminderDraft, parse_reminder_text
from nudge_bot.storage.models import Draft, Reminder
from nudge_bot.storage.unit_of_work import UnitOfWork

TextReminderOutcome = Literal["created", "draft", "unknown", "note"]
DraftActionOutcome = Literal[
    "confirmed",
    "cancelled",
    "already_confirmed",
    "already_cancelled",
    "expired",
]


@dataclass(frozen=True)
class TextReminderResult:
    outcome: TextReminderOutcome
    user_id: int
    parsed: ParsedReminderDraft
    display_timezone: str
    reminder: Reminder | None = None
    draft: Draft | None = None


@dataclass(frozen=True)
class DraftActionResult:
    outcome: DraftActionOutcome
    draft: Draft
    changed: bool
    display_timezone: str | None = None
    reminder: Reminder | None = None


async def claim_due_reminders(
    uow: UnitOfWork,
    *,
    limit: int,
    now: datetime,
) -> list[ReminderToSend]:
    return await uow.reminders.claim_due(limit=limit, now=now)


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
    timezone, zone = _safe_timezone(requested_timezone, settings.default_timezone)
    now_utc = _to_utc(now)
    parsed = parse_reminder_text(text, now=now.astimezone(zone), timezone=timezone)

    if parsed.intent_kind == "note":
        return TextReminderResult(
            outcome="note",
            user_id=user.id,
            parsed=parsed,
            display_timezone=timezone,
        )

    if parsed.due_at is None or parsed.reminder_text is None:
        return TextReminderResult(
            outcome="unknown",
            user_id=user.id,
            parsed=parsed,
            display_timezone=timezone,
        )

    if parsed.needs_confirmation:
        draft = Draft(
            user_id=user.id,
            type=DraftType.REMINDER_CONFIRMATION,
            status=DraftStatus.PENDING,
            input_text=parsed.input_text,
            parsed_text=parsed.reminder_text,
            parsed_due_at=_to_utc(parsed.due_at),
            parse_confidence=parsed.parse_confidence,
            payload={"timezone": timezone},
            expires_at=now_utc + timedelta(hours=DRAFT_EXPIRATION_HOURS),
        )
        uow.drafts.add(draft)
        await uow.session.flush()
        return TextReminderResult(
            outcome="draft",
            user_id=user.id,
            parsed=parsed,
            display_timezone=timezone,
            draft=draft,
        )

    reminder = _reminder_from_parsed(user_id=user.id, parsed=parsed)
    uow.reminders.add(reminder)
    await uow.session.flush()
    return TextReminderResult(
        outcome="created",
        user_id=user.id,
        parsed=parsed,
        display_timezone=timezone,
        reminder=reminder,
    )


async def confirm_draft(
    uow: UnitOfWork,
    *,
    draft_id: int,
    user_id: int,
    now: datetime,
) -> DraftActionResult:
    now_utc = _to_utc(now)
    draft = await uow.drafts.get_by_id_for_user_for_update(draft_id=draft_id, user_id=user_id)
    if draft is None:
        raise LookupError("draft not found")

    display_timezone = _draft_display_timezone(draft)
    if draft.status == DraftStatus.CONFIRMED:
        return DraftActionResult(
            outcome="already_confirmed",
            draft=draft,
            changed=False,
            display_timezone=display_timezone,
        )
    if draft.status == DraftStatus.CANCELLED:
        return DraftActionResult(
            outcome="already_cancelled",
            draft=draft,
            changed=False,
            display_timezone=display_timezone,
        )
    if draft.status == DraftStatus.EXPIRED:
        return DraftActionResult(
            outcome="expired",
            draft=draft,
            changed=False,
            display_timezone=display_timezone,
        )
    if _is_expired(draft, now_utc):
        draft.status = DraftStatus.EXPIRED
        draft.updated_at = now_utc
        await uow.session.flush()
        return DraftActionResult(
            outcome="expired",
            draft=draft,
            changed=True,
            display_timezone=display_timezone,
        )
    if draft.parsed_text is None or draft.parsed_due_at is None:
        raise ValueError("draft cannot be confirmed without parsed reminder fields")

    reminder = Reminder(
        user_id=user_id,
        type=ReminderType.ONE_OFF,
        status=ReminderStatus.ACTIVE,
        reminder_text=draft.parsed_text,
        due_at=draft.parsed_due_at,
        source_type=ReminderSourceType.TEXT,
        extra={},
    )
    uow.reminders.add(reminder)
    draft.status = DraftStatus.CONFIRMED
    draft.updated_at = now_utc
    await uow.session.flush()

    return DraftActionResult(
        outcome="confirmed",
        draft=draft,
        changed=True,
        display_timezone=display_timezone,
        reminder=reminder,
    )


async def cancel_draft(
    uow: UnitOfWork,
    *,
    draft_id: int,
    user_id: int,
    now: datetime,
) -> DraftActionResult:
    now_utc = _to_utc(now)
    draft = await uow.drafts.get_by_id_for_user_for_update(draft_id=draft_id, user_id=user_id)
    if draft is None:
        raise LookupError("draft not found")

    display_timezone = _draft_display_timezone(draft)
    if draft.status == DraftStatus.CANCELLED:
        return DraftActionResult(
            outcome="already_cancelled",
            draft=draft,
            changed=False,
            display_timezone=display_timezone,
        )
    if draft.status == DraftStatus.CONFIRMED:
        return DraftActionResult(
            outcome="already_confirmed",
            draft=draft,
            changed=False,
            display_timezone=display_timezone,
        )
    if draft.status == DraftStatus.EXPIRED:
        return DraftActionResult(
            outcome="expired",
            draft=draft,
            changed=False,
            display_timezone=display_timezone,
        )
    if _is_expired(draft, now_utc):
        draft.status = DraftStatus.EXPIRED
        draft.updated_at = now_utc
        await uow.session.flush()
        return DraftActionResult(
            outcome="expired",
            draft=draft,
            changed=True,
            display_timezone=display_timezone,
        )

    draft.status = DraftStatus.CANCELLED
    draft.updated_at = now_utc
    await uow.session.flush()

    return DraftActionResult(
        outcome="cancelled",
        draft=draft,
        changed=True,
        display_timezone=display_timezone,
    )


async def mark_completed(
    uow: UnitOfWork,
    *,
    reminder_id: int,
    user_id: int,
    now: datetime | None = None,
) -> ReminderResult:
    now = now or datetime.now(UTC)
    reminder = await uow.reminders.get_by_id_for_user(reminder_id=reminder_id, user_id=user_id)

    if reminder is None:
        raise LookupError("reminder not found")

    if reminder.status == ReminderStatus.COMPLETED:
        return ReminderResult(
            reminder_id=reminder_id,
            status=ReminderStatus.COMPLETED,
            changed=False,
        )

    reminder.status = ReminderStatus.COMPLETED
    reminder.completed_at = now
    reminder.locked_at = None

    return ReminderResult(reminder_id=reminder_id, status=ReminderStatus.COMPLETED, changed=True)


async def snooze(
    uow: UnitOfWork,
    *,
    reminder_id: int,
    user_id: int,
    interval_minutes: int,
    now: datetime | None = None,
) -> ReminderResult:
    now = now or datetime.now(UTC)
    reminder = await uow.reminders.get_by_id_for_user(reminder_id=reminder_id, user_id=user_id)

    if reminder is None:
        raise LookupError("reminder not found")

    if reminder.status == ReminderStatus.COMPLETED:
        return ReminderResult(
            reminder_id=reminder_id,
            status=ReminderStatus.COMPLETED,
            changed=False,
        )

    reminder.status = ReminderStatus.SNOOZED
    reminder.due_at = now + timedelta(minutes=interval_minutes)
    reminder.locked_at = None

    return ReminderResult(reminder_id=reminder_id, status=ReminderStatus.SNOOZED, changed=True)


def _reminder_from_parsed(*, user_id: int, parsed: ParsedReminderDraft) -> Reminder:
    if parsed.reminder_text is None or parsed.due_at is None:
        raise ValueError("parsed reminder must include reminder text and due time")

    return Reminder(
        user_id=user_id,
        type=ReminderType.ONE_OFF,
        status=ReminderStatus.ACTIVE,
        reminder_text=parsed.reminder_text,
        due_at=_to_utc(parsed.due_at),
        source_type=ReminderSourceType.TEXT,
        extra={},
    )


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _safe_timezone(requested_timezone: str, default_timezone: str) -> tuple[str, ZoneInfo]:
    for timezone in (requested_timezone, default_timezone, "UTC"):
        try:
            return timezone, ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            continue
    return "UTC", ZoneInfo("UTC")


def _draft_display_timezone(draft: Draft) -> str | None:
    timezone = draft.payload.get("timezone")
    return timezone if isinstance(timezone, str) else None


def _is_expired(draft: Draft, now: datetime) -> bool:
    return _to_utc(draft.expires_at) <= now
