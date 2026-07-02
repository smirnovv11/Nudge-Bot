from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from nudge_bot.constants import DEFAULT_REPEAT_INTERVAL_MINUTES, DEFAULT_TIMEZONE
from nudge_bot.reminders.enums import (
    CallbackAction,
    CallbackEventStatus,
    DraftStatus,
    DraftType,
    ReminderDeliveryStatus,
    ReminderSourceType,
    ReminderStatus,
    ReminderType,
)


class Base(DeclarativeBase):
    pass


def enum_values(enum_class: type) -> list[str]:
    return [member.value for member in enum_class]


def postgres_enum(enum_class: type, name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        values_callable=enum_values,
        validate_strings=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str | None] = mapped_column(Text)

    settings: Mapped[UserSettings] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reminders: Mapped[list[Reminder]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserSettings(TimestampMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default=DEFAULT_TIMEZONE)
    repeat_interval_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_REPEAT_INTERVAL_MINUTES,
    )

    user: Mapped[User] = relationship(back_populates="settings")


class Reminder(TimestampMixin, Base):
    __tablename__ = "reminders"
    __table_args__ = (
        Index(
            "reminders_due_deliverable_idx",
            "due_at",
            "id",
            postgresql_where=text(
                "archived_at IS NULL AND status IN ('active', 'snoozed', 'sent')"
            ),
        ),
        Index(
            "reminders_sending_locked_idx",
            "locked_at",
            postgresql_where=text("status = 'sending'"),
        ),
        Index("reminders_user_status_due_idx", "user_id", "status", "due_at"),
        Index(
            "reminders_user_completed_idx",
            "user_id",
            text("completed_at DESC"),
            postgresql_where=text("status = 'completed' AND archived_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[ReminderType] = mapped_column(
        postgres_enum(ReminderType, "reminder_type"),
        default=ReminderType.ONE_OFF,
        nullable=False,
    )
    status: Mapped[ReminderStatus] = mapped_column(
        postgres_enum(ReminderStatus, "reminder_status"),
        default=ReminderStatus.ACTIVE,
        nullable=False,
    )
    reminder_text: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[ReminderSourceType] = mapped_column(
        postgres_enum(ReminderSourceType, "reminder_source_type"),
        default=ReminderSourceType.TEXT,
        nullable=False,
    )
    extra: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="reminders")
    attempts: Mapped[list[ReminderAttempt]] = relationship(
        back_populates="reminder",
        cascade="all, delete-orphan",
    )


class ReminderAttempt(TimestampMixin, Base):
    __tablename__ = "reminder_attempts"
    __table_args__ = (
        Index(
            "reminder_attempts_reminder_attempt_uidx",
            "reminder_id",
            "attempt_no",
            unique=True,
        ),
        Index(
            "reminder_attempts_retry_idx",
            "next_retry_at",
            "id",
            postgresql_where=text("delivery_status = 'failed' AND next_retry_at IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reminder_id: Mapped[int] = mapped_column(
        ForeignKey("reminders.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    delivery_status: Mapped[ReminderDeliveryStatus] = mapped_column(
        postgres_enum(ReminderDeliveryStatus, "reminder_delivery_status"),
        default=ReminderDeliveryStatus.PENDING,
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reminder: Mapped[Reminder] = relationship(back_populates="attempts")


class Draft(TimestampMixin, Base):
    __tablename__ = "drafts"
    __table_args__ = (
        Index(
            "drafts_user_pending_idx",
            "user_id",
            text("created_at DESC"),
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "drafts_expiration_idx",
            "expires_at",
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "drafts_user_pending_edit_time_uidx",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending' AND type = 'reminder_edit_time'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[DraftType] = mapped_column(
        postgres_enum(DraftType, "draft_type"),
        nullable=False,
    )
    status: Mapped[DraftStatus] = mapped_column(
        postgres_enum(DraftStatus, "draft_status"),
        default=DraftStatus.PENDING,
        nullable=False,
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_text: Mapped[str | None] = mapped_column(Text)
    parsed_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parse_confidence: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CallbackEvent(TimestampMixin, Base):
    __tablename__ = "callback_events"
    __table_args__ = (
        Index(
            "callback_events_reminder_created_idx",
            "reminder_id",
            text("created_at DESC"),
        ),
        Index(
            "callback_events_user_created_idx",
            "user_id",
            text("created_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reminder_id: Mapped[int | None] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"))
    callback_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    action: Mapped[CallbackAction] = mapped_column(
        postgres_enum(CallbackAction, "callback_action"),
        nullable=False,
    )
    status: Mapped[CallbackEventStatus] = mapped_column(
        postgres_enum(CallbackEventStatus, "callback_event_status"),
        default=CallbackEventStatus.RECEIVED,
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
