from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nudge_bot.reminders.enums import DraftStatus
from nudge_bot.storage.models import Draft


class DraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pending_for_user(self, user_id: int) -> Draft | None:
        return await self._session.scalar(
            select(Draft)
            .where(Draft.user_id == user_id, Draft.status == DraftStatus.PENDING)
            .order_by(Draft.created_at.desc())
            .limit(1)
        )

    async def get_by_id_for_user(self, *, draft_id: int, user_id: int) -> Draft | None:
        return await self._session.scalar(
            select(Draft).where(Draft.id == draft_id, Draft.user_id == user_id)
        )

    async def get_by_id_for_user_for_update(self, *, draft_id: int, user_id: int) -> Draft | None:
        return await self._session.scalar(
            select(Draft).where(Draft.id == draft_id, Draft.user_id == user_id).with_for_update()
        )

    def add(self, draft: Draft) -> None:
        self._session.add(draft)
