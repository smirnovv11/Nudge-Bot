from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nudge_bot.constants import DEFAULT_REPEAT_INTERVAL_MINUTES, DEFAULT_TIMEZONE
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
        user_id = await self._session.scalar(
            insert(User)
            .values(
                telegram_user_id=telegram_user_id,
                username=username,
                locale=locale,
            )
            .on_conflict_do_update(
                index_elements=[User.telegram_user_id],
                set_={
                    "username": username,
                    "locale": locale,
                    "updated_at": func.now(),
                },
            )
            .returning(User.id)
        )
        if user_id is None:
            raise RuntimeError("user upsert did not return an id")

        await self._session.execute(
            insert(UserSettings)
            .values(
                user_id=user_id,
                timezone=timezone,
                repeat_interval_minutes=repeat_interval_minutes,
            )
            .on_conflict_do_nothing(index_elements=[UserSettings.user_id])
        )

        user = await self._session.scalar(
            select(User).options(selectinload(User.settings)).where(User.id == user_id)
        )
        if user is None:
            raise RuntimeError("user upsert returned an id that could not be loaded")

        return user

    async def update_settings(
        self,
        *,
        user_id: int,
        timezone: str | None = None,
        repeat_interval_minutes: int | None = None,
    ) -> UserSettings:
        values: dict[str, object] = {
            "user_id": user_id,
            "timezone": timezone or DEFAULT_TIMEZONE,
            "repeat_interval_minutes": repeat_interval_minutes or DEFAULT_REPEAT_INTERVAL_MINUTES,
        }
        updates: dict[str, object] = {"updated_at": func.now()}
        if timezone is not None:
            updates["timezone"] = timezone
        if repeat_interval_minutes is not None:
            updates["repeat_interval_minutes"] = repeat_interval_minutes

        if timezone is None and repeat_interval_minutes is None:
            settings = await self._session.scalar(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            if settings is not None:
                return settings

        await self._session.execute(
            insert(UserSettings)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[UserSettings.user_id],
                set_=updates,
            )
        )

        settings = await self._session.scalar(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        if settings is None:
            raise RuntimeError("user settings update did not return settings")

        return settings
