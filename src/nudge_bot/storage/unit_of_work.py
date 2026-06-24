from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nudge_bot.storage.repositories import (
    CallbackEventRepository,
    DraftRepository,
    ReminderAttemptRepository,
    ReminderRepository,
    UserRepository,
)


class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.reminders = ReminderRepository(session)
        self.drafts = DraftRepository(session)
        self.callback_events = CallbackEventRepository(session)
        self.attempts = ReminderAttemptRepository(session)


@asynccontextmanager
async def unit_of_work(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[UnitOfWork]:
    async with session_factory() as session:
        async with session.begin():
            yield UnitOfWork(session)
