from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nudge_bot.reminders.enums import DraftStatus, DraftType
from nudge_bot.storage.models import Draft
from nudge_bot.storage.repositories.drafts import DraftRepository


class CapturingSession:
    def __init__(self, draft: Draft) -> None:
        self.draft = draft
        self.scalar_statement: object | None = None

    async def scalar(self, statement: object) -> Draft:
        self.scalar_statement = statement
        return self.draft


@pytest.mark.asyncio
async def test_get_pending_by_type_for_user_filters_by_type_and_pending_status() -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    draft = Draft(
        id=1,
        user_id=10,
        type=DraftType.REMINDER_EDIT_TIME,
        status=DraftStatus.PENDING,
        input_text="",
        payload={"reminder_id": 1},
        expires_at=now + timedelta(hours=12),
    )
    session = CapturingSession(draft)

    result = await DraftRepository(session).get_pending_by_type_for_user(  # type: ignore[arg-type]
        user_id=10,
        draft_type=DraftType.REMINDER_EDIT_TIME,
    )

    assert result is draft
    assert session.scalar_statement is not None
    params = session.scalar_statement.compile().params  # type: ignore[attr-defined]
    assert params["user_id_1"] == 10
    assert params["type_1"] == DraftType.REMINDER_EDIT_TIME
    assert params["status_1"] == DraftStatus.PENDING
