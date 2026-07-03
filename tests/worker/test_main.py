from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from aiogram.exceptions import AiogramError

from nudge_bot.constants import DEFAULT_REPEAT_INTERVAL_MINUTES
from nudge_bot.reminders.domain import ReminderToSend
from nudge_bot.reminders.enums import ReminderStatusEnum
from nudge_bot.worker import main as worker_main
from tests.reminders.services.fakes import FakeReminder, FakeReminderRepository, FakeUnitOfWork


@dataclass
class FakeBot:
    sent_messages: list[dict[str, object]]
    deleted_messages: list[dict[str, object]]
    edited_reply_markups: list[dict[str, object]]

    async def send_message(self, **kwargs: object) -> SimpleNamespace:
        self.sent_messages.append(kwargs)
        return SimpleNamespace(message_id=1001)

    async def delete_message(self, **kwargs: object) -> None:
        self.deleted_messages.append(kwargs)

    async def edit_message_reply_markup(self, **kwargs: object) -> None:
        self.edited_reply_markups.append(kwargs)


@dataclass
class SequencedFakeBot(FakeBot):
    next_message_id: int = 1001

    async def send_message(self, **kwargs: object) -> SimpleNamespace:
        self.sent_messages.append(kwargs)
        message_id = self.next_message_id
        self.next_message_id += 1
        return SimpleNamespace(message_id=message_id)


@dataclass
class DeleteFailingBot(FakeBot):
    async def delete_message(self, **_kwargs: object) -> None:
        raise AiogramError("message cannot be deleted")


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


class ClaimingReminderListRepository(FakeReminderRepository):
    def __init__(self, reminders_to_send: list[ReminderToSend]) -> None:
        super().__init__()
        self.reminders_to_send = reminders_to_send

    async def claim_due(self, *, limit: int, now: datetime) -> list[ReminderToSend]:
        self.claim_due_called_with = (limit, now)
        return self.reminders_to_send


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
        status=ReminderStatusEnum.SENDING,
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
    bot = FakeBot(sent_messages=[], deleted_messages=[], edited_reply_markups=[])

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
    assert reminder.status == ReminderStatusEnum.SENT
    assert delivery_uow.reminders.mark_delivery_sent_called_with is not None
    assert (
        delivery_uow.reminders.mark_delivery_sent_called_with["repeat_interval_minutes"]
        == DEFAULT_REPEAT_INTERVAL_MINUTES
    )
    assert delivery_uow.attempts.attempts[0].telegram_message_id == 1001
    assert bot.deleted_messages == []


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
        status=ReminderStatusEnum.SENDING,
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
    assert reminder.status == ReminderStatusEnum.ACTIVE
    assert delivery_uow.attempts.attempts[0].error_code == "AiogramError"


@pytest.mark.asyncio
async def test_worker_tick_deletes_previous_message_after_auto_repeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    reminder_to_send = ReminderToSend(
        reminder_id=1,
        user_id=10,
        telegram_user_id=100,
        reminder_text="walk the dog",
        due_at=now,
        repeat_interval_minutes=DEFAULT_REPEAT_INTERVAL_MINUTES,
        is_auto_repeat=True,
        previous_telegram_message_id=9001,
    )
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.SENDING,
        due_at=now,
        locked_at=now,
    )
    claim_uow = FakeUnitOfWork(ClaimingReminderRepository(reminder_to_send))
    delivery_uow = FakeUnitOfWork(FakeReminderRepository(reminder))
    uows = [claim_uow, delivery_uow, delivery_uow]

    @asynccontextmanager
    async def fake_unit_of_work(_session_factory: object):
        yield uows.pop(0)

    monkeypatch.setattr(worker_main, "unit_of_work", fake_unit_of_work)
    bot = FakeBot(sent_messages=[], deleted_messages=[], edited_reply_markups=[])

    delivered = await worker_main.run_worker_tick(
        bot=bot,  # type: ignore[arg-type]
        session_factory=object(),  # type: ignore[arg-type]
        logger=FakeLogger(warnings=[]),  # type: ignore[arg-type]
        now=now,
        limit=50,
    )

    assert delivered == 1
    assert bot.deleted_messages == [{"chat_id": 100, "message_id": 9001}]
    assert bot.edited_reply_markups == []


@pytest.mark.asyncio
async def test_worker_tick_deletes_each_previous_message_for_multiple_auto_repeats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    reminders_to_send = [
        ReminderToSend(
            reminder_id=1,
            user_id=10,
            telegram_user_id=100,
            reminder_text="walk the dog",
            due_at=now,
            repeat_interval_minutes=DEFAULT_REPEAT_INTERVAL_MINUTES,
            is_auto_repeat=True,
            previous_telegram_message_id=9001,
        ),
        ReminderToSend(
            reminder_id=2,
            user_id=10,
            telegram_user_id=100,
            reminder_text="drink water",
            due_at=now,
            repeat_interval_minutes=DEFAULT_REPEAT_INTERVAL_MINUTES,
            is_auto_repeat=True,
            previous_telegram_message_id=9002,
        ),
    ]
    reminders = {
        1: FakeReminder(
            id=1,
            user_id=10,
            status=ReminderStatusEnum.SENDING,
            due_at=now,
            locked_at=now,
        ),
        2: FakeReminder(
            id=2,
            user_id=10,
            status=ReminderStatusEnum.SENDING,
            due_at=now,
            locked_at=now,
        ),
    }
    claim_uow = FakeUnitOfWork(ClaimingReminderListRepository(reminders_to_send))
    first_delivery_uow = FakeUnitOfWork(FakeReminderRepository(reminders[1]))
    second_delivery_uow = FakeUnitOfWork(FakeReminderRepository(reminders[2]))
    uows = [
        claim_uow,
        first_delivery_uow,
        first_delivery_uow,
        second_delivery_uow,
        second_delivery_uow,
    ]

    @asynccontextmanager
    async def fake_unit_of_work(_session_factory: object):
        yield uows.pop(0)

    monkeypatch.setattr(worker_main, "unit_of_work", fake_unit_of_work)
    bot = SequencedFakeBot(
        sent_messages=[],
        deleted_messages=[],
        edited_reply_markups=[],
    )

    delivered = await worker_main.run_worker_tick(
        bot=bot,  # type: ignore[arg-type]
        session_factory=object(),  # type: ignore[arg-type]
        logger=FakeLogger(warnings=[]),  # type: ignore[arg-type]
        now=now,
        limit=50,
    )

    assert delivered == 2
    assert "walk the dog" in str(bot.sent_messages[0]["text"])
    assert "drink water" in str(bot.sent_messages[1]["text"])
    assert bot.deleted_messages == [
        {"chat_id": 100, "message_id": 9001},
        {"chat_id": 100, "message_id": 9002},
    ]


@pytest.mark.asyncio
async def test_worker_tick_removes_old_keyboard_when_previous_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    reminder_to_send = ReminderToSend(
        reminder_id=1,
        user_id=10,
        telegram_user_id=100,
        reminder_text="walk the dog",
        due_at=now,
        repeat_interval_minutes=DEFAULT_REPEAT_INTERVAL_MINUTES,
        is_auto_repeat=True,
        previous_telegram_message_id=9001,
    )
    reminder = FakeReminder(
        id=1,
        user_id=10,
        status=ReminderStatusEnum.SENDING,
        due_at=now,
        locked_at=now,
    )
    claim_uow = FakeUnitOfWork(ClaimingReminderRepository(reminder_to_send))
    delivery_uow = FakeUnitOfWork(FakeReminderRepository(reminder))
    uows = [claim_uow, delivery_uow, delivery_uow]

    @asynccontextmanager
    async def fake_unit_of_work(_session_factory: object):
        yield uows.pop(0)

    monkeypatch.setattr(worker_main, "unit_of_work", fake_unit_of_work)
    bot = DeleteFailingBot(sent_messages=[], deleted_messages=[], edited_reply_markups=[])
    logger = FakeLogger(warnings=[])

    delivered = await worker_main.run_worker_tick(
        bot=bot,  # type: ignore[arg-type]
        session_factory=object(),  # type: ignore[arg-type]
        logger=logger,  # type: ignore[arg-type]
        now=now,
        limit=50,
    )

    assert delivered == 1
    assert bot.edited_reply_markups == [{"chat_id": 100, "message_id": 9001, "reply_markup": None}]
    assert logger.warnings[0]["message"] == "worker: previous reminder message delete failed"
