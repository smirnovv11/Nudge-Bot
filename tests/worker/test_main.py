from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from aiogram.exceptions import AiogramError

from nudge_bot.constants import DEFAULT_REPEAT_INTERVAL_MINUTES
from nudge_bot.reminders.domain import ReminderToSend
from nudge_bot.reminders.enums import ReminderStatus
from nudge_bot.worker import main as worker_main
from tests.reminders.services.fakes import FakeReminder, FakeReminderRepository, FakeUnitOfWork


@dataclass
class FakeBot:
    sent_messages: list[dict[str, object]]

    async def send_message(self, **kwargs: object) -> SimpleNamespace:
        self.sent_messages.append(kwargs)
        return SimpleNamespace(message_id=1001)


@dataclass
class FailingBot:
    async def send_message(self, **_kwargs: object) -> SimpleNamespace:
        raise AiogramError("network down")


@dataclass
class FakeLogger:
    warnings: list[dict[str, object]]

    def debug(self, *_args: object, **_kwargs: object) -> None:
        return None

    def warning(self, message: str, **kwargs: object) -> None:
        self.warnings.append({"message": message, **kwargs})


class ClaimingReminderRepository(FakeReminderRepository):
    def __init__(self, reminder_to_send: ReminderToSend) -> None:
        super().__init__()
        self.reminder_to_send = reminder_to_send

    async def claim_due(self, *, limit: int, now: datetime) -> list[ReminderToSend]:
        self.claim_due_called_with = (limit, now)
        return [self.reminder_to_send]


@pytest.mark.asyncio
async def test_worker_tick_sends_claimed_reminder(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    reminder_to_send = ReminderToSend(
        reminder_id=1,
        user_id=10,
        telegram_user_id=100,
        reminder_text="walk the dog",
        due_at=now,
        repeat_interval_minutes=DEFAULT_REPEAT_INTERVAL_MINUTES,
    )
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatus.SENDING,
        due_at=now,
        locked_at=now,
    )
    claim_uow = FakeUnitOfWork(ClaimingReminderRepository(reminder_to_send))
    delivery_uow = FakeUnitOfWork(FakeReminderRepository(reminder))
    success_uow = delivery_uow
    uows = [claim_uow, delivery_uow, success_uow]

    @asynccontextmanager
    async def fake_unit_of_work(_session_factory: object):
        yield uows.pop(0)

    monkeypatch.setattr(worker_main, "unit_of_work", fake_unit_of_work)
    bot = FakeBot(sent_messages=[])

    delivered = await worker_main.run_worker_tick(
        bot=bot,  # type: ignore[arg-type]
        session_factory=object(),  # type: ignore[arg-type]
        logger=FakeLogger(warnings=[]),  # type: ignore[arg-type]
        now=now,
        limit=50,
    )

    assert delivered == 1
    assert bot.sent_messages[0]["chat_id"] == 100
    assert bot.sent_messages[0]["text"] == "⏰ <i>Reminder</i>\n\n📨 walk the dog"
    assert bot.sent_messages[0]["parse_mode"] == "HTML"
    assert reminder.status == ReminderStatus.SENT
    assert delivery_uow.reminders.mark_delivery_sent_called_with is not None
    assert (
        delivery_uow.reminders.mark_delivery_sent_called_with["repeat_interval_minutes"]
        == DEFAULT_REPEAT_INTERVAL_MINUTES
    )
    assert delivery_uow.attempts.attempts[0].telegram_message_id == 1001


@pytest.mark.asyncio
async def test_worker_tick_records_send_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    reminder_to_send = ReminderToSend(
        reminder_id=1,
        user_id=10,
        telegram_user_id=100,
        reminder_text="walk the dog",
        due_at=now,
        repeat_interval_minutes=DEFAULT_REPEAT_INTERVAL_MINUTES,
    )
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatus.SENDING,
        due_at=now,
        locked_at=now,
    )
    claim_uow = FakeUnitOfWork(ClaimingReminderRepository(reminder_to_send))
    delivery_uow = FakeUnitOfWork(FakeReminderRepository(reminder))
    failure_uow = delivery_uow
    uows = [claim_uow, delivery_uow, failure_uow]

    @asynccontextmanager
    async def fake_unit_of_work(_session_factory: object):
        yield uows.pop(0)

    monkeypatch.setattr(worker_main, "unit_of_work", fake_unit_of_work)

    delivered = await worker_main.run_worker_tick(
        bot=FailingBot(),  # type: ignore[arg-type]
        session_factory=object(),  # type: ignore[arg-type]
        logger=FakeLogger(warnings=[]),  # type: ignore[arg-type]
        now=now,
        limit=50,
    )

    assert delivered == 1
    assert reminder.status == ReminderStatus.ACTIVE
    assert delivery_uow.attempts.attempts[0].error_code == "AiogramError"
