"""
Question, QuestionOption, QuestionMedia ORM models — mirror `questions`,
`question_options`, `question_media` tables in schema_v2.sql (Modules
12-14). Grouped in one module (same reasoning as permissions +
role_permissions) since none of the three makes sense without Question.
"""
import uuid
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
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

    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tests.id", ondelete="CASCADE"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(20), nullable=False, default=QuestionType.SINGLE_CHOICE)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=1)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

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
