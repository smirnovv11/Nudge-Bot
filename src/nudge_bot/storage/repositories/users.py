from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nudge_bot.storage.models import User, UserSettings


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return await self._session.scalar(
            select(User)
            .options(selectinload(User.settings))
            .where(User.telegram_user_id == telegram_user_id)
        )

    async def get_by_id_for_update(self, user_id: int) -> User | None:
        return await self._session.scalar(select(User).where(User.id == user_id).with_for_update())

    async def get_or_create(
        self,
        *,
        telegram_user_id: int,
        username: str | None,
        locale: str | None,
        timezone: str,
        repeat_interval_minutes: int,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_user_id)
        if user is not None:
            user.username = username
            user.locale = locale
            return user

        user = User(telegram_user_id=telegram_user_id, username=username, locale=locale)
        user.settings = UserSettings(
            timezone=timezone,
            repeat_interval_minutes=repeat_interval_minutes,
        )
        self._session.add(user)
        await self._session.flush()
        return user
