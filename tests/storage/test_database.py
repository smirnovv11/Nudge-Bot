from __future__ import annotations

import pytest

from nudge_bot.storage.database import prepare_asyncpg_database_url


def test_prepare_asyncpg_database_url_translates_sslmode_require() -> None:
    url, connect_args = prepare_asyncpg_database_url(
        "postgresql+asyncpg://user:password@example.com:5432/nudge?sslmode=require"
    )

    assert "sslmode" not in url.query
    assert str(url) == "postgresql+asyncpg://user:***@example.com:5432/nudge"
    assert connect_args == {"ssl": True}


def test_prepare_asyncpg_database_url_leaves_plain_url_unchanged() -> None:
    url, connect_args = prepare_asyncpg_database_url(
        "postgresql+asyncpg://user:password@example.com:5432/nudge"
    )

    assert str(url) == "postgresql+asyncpg://user:***@example.com:5432/nudge"
    assert connect_args == {}


def test_prepare_asyncpg_database_url_rejects_unknown_sslmode() -> None:
    with pytest.raises(ValueError, match="Unsupported PostgreSQL sslmode"):
        prepare_asyncpg_database_url(
            "postgresql+asyncpg://user:password@example.com:5432/nudge?sslmode=surprise"
        )
