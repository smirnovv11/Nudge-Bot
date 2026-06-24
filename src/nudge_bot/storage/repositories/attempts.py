from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from nudge_bot.storage.models import ReminderAttempt


class ReminderAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, attempt: ReminderAttempt) -> None:
        self._session.add(attempt)
