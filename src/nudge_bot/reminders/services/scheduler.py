from __future__ import annotations

from datetime import datetime

from nudge_bot.reminders.domain import ReminderToSend
from nudge_bot.storage.unit_of_work import UnitOfWork


class ReminderSchedulerService:
    async def claim_due_reminders(
        self,
        uow: UnitOfWork,
        *,
        limit: int,
        now: datetime,
    ) -> list[ReminderToSend]:
        return await uow.reminders.claim_due(limit=limit, now=now)
