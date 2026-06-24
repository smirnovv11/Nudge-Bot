"""create reminder tables

Revision ID: 20260624_1751
Revises:
Create Date: 2026-06-24 17:51:00.000000

"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260624_1751"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


reminder_type = postgresql.ENUM("one_off", name="reminder_type", create_type=False)
reminder_status = postgresql.ENUM(
    "active",
    "sending",
    "sent",
    "snoozed",
    "completed",
    "archived",
    name="reminder_status",
    create_type=False,
)
reminder_source_type = postgresql.ENUM(
    "text",
    "voice",
    "manual",
    name="reminder_source_type",
    create_type=False,
)
reminder_delivery_status = postgresql.ENUM(
    "pending",
    "sending",
    "sent",
    "failed",
    "abandoned",
    name="reminder_delivery_status",
    create_type=False,
)
draft_type = postgresql.ENUM(
    "reminder_confirmation",
    "reminder_edit_time",
    "reminder_edit_text",
    "note_capture",
    name="draft_type",
    create_type=False,
)
draft_status = postgresql.ENUM(
    "pending",
    "confirmed",
    "cancelled",
    "expired",
    name="draft_status",
    create_type=False,
)
callback_action = postgresql.ENUM(
    "read",
    "repeat",
    "choose_time",
    "confirm",
    "edit_time",
    "edit_text",
    "cancel",
    name="callback_action",
    create_type=False,
)
callback_event_status = postgresql.ENUM(
    "received",
    "processed",
    "ignored",
    "failed",
    name="callback_event_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    reminder_type.create(bind, checkfirst=True)
    reminder_status.create(bind, checkfirst=True)
    reminder_source_type.create(bind, checkfirst=True)
    reminder_delivery_status.create(bind, checkfirst=True)
    draft_type.create(bind, checkfirst=True)
    draft_status.create(bind, checkfirst=True)
    callback_action.create(bind, checkfirst=True)
    callback_event_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("locale", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("users_telegram_user_id_uidx", "users", ["telegram_user_id"], unique=True)

    op.create_table(
        "user_settings",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="Europe/Minsk"),
        sa.Column("repeat_interval_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "reminders",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", reminder_type, nullable=False, server_default="one_off"),
        sa.Column("status", reminder_status, nullable=False, server_default="active"),
        sa.Column("reminder_text", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", reminder_source_type, nullable=False, server_default="text"),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "reminders_due_deliverable_idx",
        "reminders",
        ["due_at", "id"],
        postgresql_where=sa.text("archived_at IS NULL AND status IN ('active', 'snoozed')"),
    )
    op.create_index(
        "reminders_sending_locked_idx",
        "reminders",
        ["locked_at"],
        postgresql_where=sa.text("status = 'sending'"),
    )
    op.create_index("reminders_user_status_due_idx", "reminders", ["user_id", "status", "due_at"])
    op.create_index(
        "reminders_user_completed_idx",
        "reminders",
        ["user_id", sa.text("completed_at DESC")],
        postgresql_where=sa.text("status = 'completed' AND archived_at IS NULL"),
    )

    op.create_table(
        "reminder_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "reminder_id",
            sa.BigInteger(),
            sa.ForeignKey("reminders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "delivery_status", reminder_delivery_status, nullable=False, server_default="pending"
        ),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "reminder_attempts_reminder_attempt_uidx",
        "reminder_attempts",
        ["reminder_id", "attempt_no"],
        unique=True,
    )
    op.create_index(
        "reminder_attempts_retry_idx",
        "reminder_attempts",
        ["next_retry_at", "id"],
        postgresql_where=sa.text("delivery_status = 'failed' AND next_retry_at IS NOT NULL"),
    )

    op.create_table(
        "drafts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", draft_type, nullable=False),
        sa.Column("status", draft_status, nullable=False, server_default="pending"),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("parsed_text", sa.Text(), nullable=True),
        sa.Column("parsed_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parse_confidence", sa.Float(), nullable=True),
        sa.Column(
            "payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "drafts_user_pending_idx",
        "drafts",
        ["user_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "drafts_expiration_idx",
        "drafts",
        ["expires_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "callback_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reminder_id",
            sa.BigInteger(),
            sa.ForeignKey("reminders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("callback_key", sa.Text(), nullable=False),
        sa.Column("action", callback_action, nullable=False),
        sa.Column("status", callback_event_status, nullable=False, server_default="received"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "callback_events_callback_key_uidx", "callback_events", ["callback_key"], unique=True
    )
    op.create_index(
        "callback_events_reminder_created_idx",
        "callback_events",
        ["reminder_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "callback_events_user_created_idx",
        "callback_events",
        ["user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("callback_events_user_created_idx", table_name="callback_events")
    op.drop_index("callback_events_reminder_created_idx", table_name="callback_events")
    op.drop_index("callback_events_callback_key_uidx", table_name="callback_events")
    op.drop_table("callback_events")

    op.drop_index("drafts_expiration_idx", table_name="drafts")
    op.drop_index("drafts_user_pending_idx", table_name="drafts")
    op.drop_table("drafts")

    op.drop_index("reminder_attempts_retry_idx", table_name="reminder_attempts")
    op.drop_index("reminder_attempts_reminder_attempt_uidx", table_name="reminder_attempts")
    op.drop_table("reminder_attempts")

    op.drop_index("reminders_user_completed_idx", table_name="reminders")
    op.drop_index("reminders_user_status_due_idx", table_name="reminders")
    op.drop_index("reminders_sending_locked_idx", table_name="reminders")
    op.drop_index("reminders_due_deliverable_idx", table_name="reminders")
    op.drop_table("reminders")

    op.drop_table("user_settings")
    op.drop_index("users_telegram_user_id_uidx", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    callback_event_status.drop(bind, checkfirst=True)
    callback_action.drop(bind, checkfirst=True)
    draft_status.drop(bind, checkfirst=True)
    draft_type.drop(bind, checkfirst=True)
    reminder_delivery_status.drop(bind, checkfirst=True)
    reminder_source_type.drop(bind, checkfirst=True)
    reminder_status.drop(bind, checkfirst=True)
    reminder_type.drop(bind, checkfirst=True)
