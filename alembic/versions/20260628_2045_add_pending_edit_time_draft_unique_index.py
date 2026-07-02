"""Add unique pending edit-time draft index.

Revision ID: 20260628_2045
Revises: 20260628_1930
Create Date: 2026-06-28 20:45:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260628_2045"
down_revision: str | None = "20260628_1930"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY user_id
                        ORDER BY created_at DESC, id DESC
                    ) AS draft_rank
                FROM drafts
                WHERE status = 'pending'
                  AND type = 'reminder_edit_time'
            )
            UPDATE drafts
            SET status = 'cancelled',
                updated_at = now()
            FROM ranked
            WHERE drafts.id = ranked.id
              AND ranked.draft_rank > 1
            """
        )
    )
    op.create_index(
        "drafts_user_pending_edit_time_uidx",
        "drafts",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending' AND type = 'reminder_edit_time'"),
    )


def downgrade() -> None:
    op.drop_index("drafts_user_pending_edit_time_uidx", table_name="drafts")
