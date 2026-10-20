"""
Question, QuestionOption, QuestionMedia ORM models — mirror `questions`,
`question_options`, `question_media` tables in schema_v2.sql (Modules
12-14). Grouped in one module (same reasoning as permissions +
role_permissions) since none of the three makes sense without Question.
"""
import uuid
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class QuestionType(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"


class Question(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "answer_format IS NULL OR answer_format IN ('text', 'numeric')",
            name="ck_questions_answer_format_allowed",
        ),
        CheckConstraint(
            "answer_format IS NULL OR question_type = 'short_answer'",
            name="ck_questions_answer_format_short_answer_only",
        ),
        CheckConstraint(
            "numeric_tolerance IS NULL OR (answer_format = 'numeric' AND numeric_tolerance >= 0)",
            name="ck_questions_numeric_tolerance_numeric_only",
        ),
    )

    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tests.id", ondelete="CASCADE"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(20), nullable=False, default=QuestionType.SINGLE_CHOICE)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=1)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Sprint 45 — additive. NULL for every existing question (a
    # question with no section, exactly as before this sprint). Optional
    # link to a Generic Exam Engine section (e.g. SAT's "Math",
    # IELTS's "Listening") — SET NULL on section delete so removing a
    # section never cascades into deleting questions.
    section_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_sections.id", ondelete="SET NULL"), nullable=True)
    # Sprint 46 — additive. NULL for every existing question (a
    # question with no module, exactly as before this sprint).
    # Optional link to a Generic Exam Engine module (e.g. SAT's
    # "Module 1" within the "Math" section) — SET NULL on module
    # delete, same reasoning as section_id above.
    module_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_modules.id", ondelete="SET NULL"), nullable=True)
    # Sprint 47 — additive. NULL for every existing question. Optional
    # link to a shared QuestionGroup (e.g. an IELTS Reading passage's
    # set of questions) — SET NULL on group delete.
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("question_groups.id", ondelete="SET NULL"), nullable=True)

    # Task 2 (migration 0023) — automatic grading for short_answer.
    # answer_format NULL = not auto-graded (manual review; the exact
    # pre-0023 behavior for every existing row). See
    # questions/answer_matching.py for the grading rules. NEVER exposed
    # to students: attempts/schemas.QuestionForAttemptOut is built field
    # by field and does not carry any of these.
    answer_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    accepted_answers: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    numeric_tolerance: Mapped[float | None] = mapped_column(Numeric(20, 10), nullable=True)

    options: Mapped[list["QuestionOption"]] = relationship(back_populates="question", cascade="all, delete-orphan")
    media: Mapped[list["QuestionMedia"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class QuestionOption(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "question_options"

    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    question: Mapped["Question"] = relationship(back_populates="options")


class QuestionMedia(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "question_media"

    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    # Sprint 32 — additive. NULL means this media belongs to the option
    # specified (option-level media, Phase 7); set means it belongs to
    # the question as a whole (existing, unchanged default behavior).
    option_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("question_options.id", ondelete="CASCADE"), nullable=True,
    )
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    # Sprint 32 — additive. When set, this media is a REAL, R2-backed
    # Upload row (signed-URL access, ownership-checked) rather than an
    # arbitrary client-supplied URL. NULL for legacy rows / the
    # existing raw-file_url path, kept for backward compatibility.
    upload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True)

    question: Mapped["Question"] = relationship(back_populates="media")
