from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nudge_bot.storage.models import CallbackEvent


class CallbackEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_key(self, callback_key: str) -> CallbackEvent | None:
        return await self._session.scalar(
            select(CallbackEvent).where(CallbackEvent.callback_key == callback_key)
        )

    def add(self, event: CallbackEvent) -> None:
        self._session.add(event)
