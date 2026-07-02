from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from nudge_bot.config import Settings, get_settings


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    settings = settings or get_settings()
    database_url, connect_args = prepare_asyncpg_database_url(settings.database_url)
    return create_async_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


def prepare_asyncpg_database_url(database_url: str) -> tuple[URL, dict[str, Any]]:
    url = make_url(database_url)
    connect_args: dict[str, Any] = {}

    if url.drivername != "postgresql+asyncpg" or "sslmode" not in url.query:
        return url, connect_args

    sslmode = url.query["sslmode"]
    if isinstance(sslmode, tuple):
        sslmode = sslmode[-1]

    url = url.difference_update_query(["sslmode"])
    connect_args["ssl"] = asyncpg_ssl_from_sslmode(sslmode)
    return url, connect_args


def asyncpg_ssl_from_sslmode(sslmode: str) -> bool:
    match sslmode.lower():
        case "disable":
            return False
        case "allow" | "prefer" | "require" | "verify-ca" | "verify-full":
            return True
        case _:
            raise ValueError(f"Unsupported PostgreSQL sslmode for asyncpg: {sslmode}")


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        async with session.begin():
            yield session
