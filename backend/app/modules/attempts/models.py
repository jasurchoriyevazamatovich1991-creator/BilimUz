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

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
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
    # Sprint 58 — added to the ORM model (NOT a new migration: this
    # constraint has existed in the database since the very first
    # schema, migration 0001_initial_schema.py line ~535 — "CONSTRAINT
    # uq_answers_attempt_question UNIQUE (attempt_id, question_id)" —
    # but the SQLAlchemy model never declared it, a model/DB drift
    # discovered while implementing this sprint's audited fix. Because
    # the constraint was always there, a duplicate Answer row was never
    # actually possible; what save_answer()'s old check-then-act
    # (get() then create()/update()) could actually produce was an
    # UNHANDLED IntegrityError (a 500) for the losing side of a race,
    # since create() never expected the insert to be rejected. See
    # AnswerRepository.upsert(), which now handles the conflict
    # gracefully via this exact constraint instead of crashing.
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_answers_attempt_question"),)

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    selected_option: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("question_options.id"), nullable=True)
    # Sprint 30 — additive. NULL for every single_choice/true_false
    # answer (they keep using selected_option above, unchanged).
    # Populated only for multiple_choice answers.
    selected_options: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="answered")
    # Sprint 45 — additive. Storage foundation only: QuestionType.SHORT_ANSWER
    # and .ESSAY have existed since the earliest sprints, but Answer had
    # nowhere to store a text response (verified directly against this
    # model before this sprint — only selected_option/selected_options
    # existed). NULL for every existing answer and for every
    # choice-based answer (selected_option/selected_options are still
    # how those are recorded, completely unchanged). Grading/scoring of
    # a free-text answer is explicitly out of scope for this sprint.
    text_answer: Mapped[str | None] = mapped_column(Text, nullable=True)


class AttemptModuleProgress(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Sprint 46 — Generic Exam Module foundation. Records a single
    attempt's progress through one ExamModule. Nothing in this sprint
    creates a row here automatically for every attempt — an attempt
    against a moduleless test (every existing Physics/National
    Certificate test) simply never has any AttemptModuleProgress rows,
    exactly as before this table existed.

    question_order reuses TestAttempt.question_order's own established
    pattern (an ARRAY of question UUIDs, persisted at module-start
    time) rather than a separate association table — Sprint 6's
    original "persist, not compute" reasoning for the whole-test
    version applies identically here: once snapshotted, a later change
    to the module's live question set (Question.module_id assignments)
    must never retroactively change an already-started attempt's
    ordering. Reusing the proven pattern here also means no new
    association table (attempt_module_questions) was needed — see the
    Sprint 46 revision audit's point 2.

    status reuses attempts.models.AttemptStatus's own values (no new
    enum introduced) for the same reason: a module's progress is the
    same kind of state machine (in_progress -> submitted, etc.) the
    project already has one name for.
    """
    __tablename__ = "attempt_module_progress"
    __table_args__ = (UniqueConstraint("attempt_id", "module_id", name="uq_attempt_module_progress_attempt_id_module_id"),)

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False)
    module_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_modules.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AttemptStatus.IN_PROGRESS)
    question_order: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
