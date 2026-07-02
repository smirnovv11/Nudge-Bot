"""Include sent reminders in due reminder index.

Revision ID: 20260628_1930
Revises: 20260626_2130
Create Date: 2026-06-28 19:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260628_1930"
down_revision: str | None = "20260626_2130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("reminders_due_deliverable_idx", table_name="reminders")
    op.create_index(
        "reminders_due_deliverable_idx",
        "reminders",
        ["due_at", "id"],
        postgresql_where=sa.text("archived_at IS NULL AND status IN ('active', 'snoozed', 'sent')"),
    )


def downgrade() -> None:
    op.drop_index("reminders_due_deliverable_idx", table_name="reminders")
    op.create_index(
        "reminders_due_deliverable_idx",
        "reminders",
        ["due_at", "id"],
        postgresql_where=sa.text("archived_at IS NULL AND status IN ('active', 'snoozed')"),
    )
