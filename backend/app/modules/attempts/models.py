"""
TestAttempt, Answer ORM models — mirror `test_attempts` and `answers`
tables in schema_v2.sql (Module 15), PLUS the two columns added by
Alembic migration 0002 (expires_at, question_order) per the Sprint 6
architecture decision to persist, not compute, timer/randomization state.

Neither table has created_by/updated_by (verified against schema_v2.sql)
— no AuditMixin here, unlike every content-management module.
"""
import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class AttemptStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    SUBMITTED = "submitted"
    AUTO_FINISHED = "auto_finished"
    CANCELLED = "cancelled"


class TestAttempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "test_attempts"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tests.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finish_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AttemptStatus.IN_PROGRESS)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    question_order: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)


class Answer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "answers"

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    selected_option: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("question_options.id"), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="answered")
