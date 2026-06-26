from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nudge_bot.reminders.enums import ReminderDeliveryStatus, ReminderStatus
from nudge_bot.reminders.services import ReminderDeliveryService

from .fakes import FakeReminder, FakeReminderRepository, FakeUnitOfWork


@pytest.mark.asyncio
async def test_delivery_success_marks_reminder_sent_and_records_attempt() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatus.SENDING,
        due_at=now,
        locked_at=now,
    )
    uow = FakeUnitOfWork(FakeReminderRepository(reminder))
    service = ReminderDeliveryService()

    attempt = await service.create_sending_attempt(uow, reminder_id=1, scheduled_for=now)
    await service.mark_sent(
        uow,
        reminder_id=1,
        attempt_id=attempt.id,
        telegram_message_id=1001,
        now=now,
    )

    stored_attempt = uow.attempts.attempts[0]
    assert reminder.status == ReminderStatus.SENT
    assert reminder.locked_at is None
    assert stored_attempt.delivery_status == ReminderDeliveryStatus.SENT
    assert stored_attempt.telegram_message_id == 1001


@pytest.mark.asyncio
async def test_delivery_failure_returns_reminder_to_active_and_records_attempt() -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatus.SENDING,
        due_at=now,
        locked_at=now,
    )
    uow = FakeUnitOfWork(FakeReminderRepository(reminder))
    service = ReminderDeliveryService()

    attempt = await service.create_sending_attempt(uow, reminder_id=1, scheduled_for=now)
    await service.mark_failed(
        uow,
        reminder_id=1,
        attempt_id=attempt.id,
        error_code="TelegramNetworkError",
        error_message="network down",
    )

    stored_attempt = uow.attempts.attempts[0]
    assert reminder.status == ReminderStatus.ACTIVE
    assert reminder.locked_at is None
    assert stored_attempt.delivery_status == ReminderDeliveryStatus.FAILED
    assert stored_attempt.error_code == "TelegramNetworkError"
