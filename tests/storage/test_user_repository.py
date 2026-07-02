from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from nudge_bot.storage.models import User
from nudge_bot.storage.repositories.users import UserRepository


class CapturingSession:
    def __init__(self, user: User) -> None:
        self.user = user
        self.scalar_statements: list[object] = []
        self.executed_statements: list[object] = []

    async def scalar(self, statement: object) -> int | User:
        self.scalar_statements.append(statement)
        if len(self.scalar_statements) == 1:
            return self.user.id
        return self.user

    async def execute(self, statement: object) -> None:
        self.executed_statements.append(statement)


@pytest.mark.asyncio
async def test_get_or_create_upserts_user_and_inserts_settings_once() -> None:
    user = User(id=1, telegram_user_id=1129873105, username="smirnovv112", locale="en")
    session = CapturingSession(user)

    result = await UserRepository(session).get_or_create(  # type: ignore[arg-type]
        telegram_user_id=1129873105,
        username="smirnovv112",
        locale="en",
        timezone="Europe/Minsk",
        repeat_interval_minutes=5,
    )

    assert result is user

    user_upsert = _compile_sql(session.scalar_statements[0])
    assert "INSERT INTO users" in user_upsert
    assert "ON CONFLICT (telegram_user_id) DO UPDATE" in user_upsert
    assert "RETURNING users.id" in user_upsert

    settings_insert = _compile_sql(session.executed_statements[0])
    assert "INSERT INTO user_settings" in settings_insert
    assert "ON CONFLICT (user_id) DO NOTHING" in settings_insert

    user_reload = _compile_sql(session.scalar_statements[1])
    assert "FROM users" in user_reload
    assert "WHERE users.id" in user_reload


def _compile_sql(statement: object) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]
