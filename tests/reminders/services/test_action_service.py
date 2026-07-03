from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nudge_bot.constants import DEFAULT_REPEAT_INTERVAL_MINUTES
from nudge_bot.reminders.enums import (
    CallbackActionEnum,
    CallbackEventStatusEnum,
    ReminderStatusEnum,
)
from nudge_bot.reminders.services import ReminderActionService

from .fakes import (
    FakeCallbackEvent,
    FakeCallbackEventRepository,
    FakeReminder,
    FakeReminderRepository,
    FakeUnitOfWork,
)


@pytest.mark.asyncio
async def test_mark_completed_is_idempotent_for_completed_reminder() -> None:
    completed_at = datetime(2026, 6, 24, 11, 0, tzinfo=UTC)
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.COMPLETED,
        due_at=completed_at,
        completed_at=completed_at,
    )

    result = await ReminderActionService().mark_completed(
        FakeUnitOfWork(FakeReminderRepository(reminder)),
        reminder_id=1,
        user_id=10,
        now=datetime(2026, 6, 24, 12, 0, tzinfo=UTC),
    )

    assert result.status == ReminderStatusEnum.COMPLETED
    assert result.changed is False
    assert reminder.completed_at == completed_at


@pytest.mark.asyncio
async def test_snooze_updates_due_time_for_active_reminder() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.ACTIVE,
        due_at=now,
        locked_at=now,
    )

    result = await ReminderActionService().snooze(
        FakeUnitOfWork(FakeReminderRepository(reminder)),
        reminder_id=1,
        user_id=10,
        interval_minutes=DEFAULT_REPEAT_INTERVAL_MINUTES,
        now=now,
    )

    assert result.status == ReminderStatusEnum.SNOOZED
    assert result.changed is True
    assert reminder.status == ReminderStatusEnum.SNOOZED
    assert reminder.due_at == now + timedelta(minutes=DEFAULT_REPEAT_INTERVAL_MINUTES)
    assert reminder.locked_at is None


@pytest.mark.asyncio
async def test_repeated_repeat_callback_does_not_move_due_time_twice() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    due_at = now + timedelta(minutes=DEFAULT_REPEAT_INTERVAL_MINUTES)
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.SNOOZED,
        due_at=due_at,
    )
    event = FakeCallbackEvent(
        user_id=10,
        reminder_id=1,
        callback_key="reminder:1:notification:7:action:repeat",
        action=CallbackActionEnum.REPEAT,
        status=CallbackEventStatusEnum.PROCESSED,
    )

    result = await ReminderActionService().process_callback_action(
        FakeUnitOfWork(
            FakeReminderRepository(reminder),
            callback_events=FakeCallbackEventRepository(event),
        ),
        callback_key="reminder:1:notification:7:action:repeat",
        action=CallbackActionEnum.REPEAT,
        reminder_id=1,
        user_id=10,
        interval_minutes=DEFAULT_REPEAT_INTERVAL_MINUTES,
        now=now + timedelta(minutes=1),
    )

    assert result.changed is False
    assert reminder.due_at == due_at


@pytest.mark.asyncio
async def test_repeated_repeat_callback_reschedules_stale_due_time_from_now() -> None:
    previous_due_at = datetime(2026, 6, 26, 21, 46, tzinfo=UTC)
    now = datetime(2026, 6, 27, 0, 41, tzinfo=UTC)
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.SNOOZED,
        due_at=previous_due_at,
    )
    event = FakeCallbackEvent(
        user_id=10,
        reminder_id=1,
        callback_key="reminder:1:notification:7:action:repeat",
        action=CallbackActionEnum.REPEAT,
        status=CallbackEventStatusEnum.PROCESSED,
    )

    result = await ReminderActionService().process_callback_action(
        FakeUnitOfWork(
            FakeReminderRepository(reminder),
            callback_events=FakeCallbackEventRepository(event),
        ),
        callback_key="reminder:1:notification:7:action:repeat",
        action=CallbackActionEnum.REPEAT,
        reminder_id=1,
        user_id=10,
        interval_minutes=DEFAULT_REPEAT_INTERVAL_MINUTES,
        now=now,
    )

    assert result.changed is True
    assert reminder.status == ReminderStatusEnum.SNOOZED
    assert reminder.due_at == now + timedelta(minutes=DEFAULT_REPEAT_INTERVAL_MINUTES)


@pytest.mark.asyncio
async def test_repeat_callback_snoozes_once_and_records_event() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.SENT,
        due_at=now,
    )
    callback_events = FakeCallbackEventRepository()
    uow = FakeUnitOfWork(
        FakeReminderRepository(reminder),
        callback_events=callback_events,
    )

    result = await ReminderActionService().process_callback_action(
        uow,
        callback_key="reminder:1:notification:7:action:repeat",
        action=CallbackActionEnum.REPEAT,
        reminder_id=1,
        user_id=10,
        interval_minutes=DEFAULT_REPEAT_INTERVAL_MINUTES,
        now=now,
    )

    assert result.changed is True
    assert reminder.status == ReminderStatusEnum.SNOOZED
    assert reminder.due_at == now + timedelta(minutes=DEFAULT_REPEAT_INTERVAL_MINUTES)
    assert callback_events.added[0].status == CallbackEventStatusEnum.PROCESSED
