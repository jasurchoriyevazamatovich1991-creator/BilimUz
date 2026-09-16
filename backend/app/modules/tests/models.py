"""Test ORM model — mirrors `tests` table in schema_v2.sql (Module 11).
Test *definition* only — the taking-experience lives in the `attempts`
module, which reads this model read-only."""
import uuid
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class DifficultyLevel(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TestStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Test(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin):
    __tablename__ = "tests"

    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("grades.id"), nullable=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default=DifficultyLevel.MEDIUM)
    duration: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passing_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    shuffle_answers: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TestStatus.DRAFT)
    # Sprint 45 — additive. NULL (every test before this sprint, and any
    # test that doesn't explicitly set it) means "use the platform
    # default" — attempts/constants.py's DEFAULT_MAX_ATTEMPTS = 1,
    # completely unchanged behavior. This is what takes max_attempts
    # out of hardcoding: a Test can now opt into a different limit
    # without any code change, but nothing changes for a Test that
    # doesn't set it.
    max_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ExamSection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Sprint 45 — Generic Exam Engine foundation. Optional grouping of
    Questions within a Test (e.g. SAT's "Reading and Writing" / "Math",
    IELTS's "Listening" / "Reading" / "Writing" / "Speaking"). A Test
    with zero sections (every existing Physics/National Certificate
    test) is completely unaffected — its Questions simply have
    section_id = NULL, the same as before this table existed.

    order_number mirrors the proven UNIQUE(topic_id, order_number)
    pattern lessons.models.Lesson established in Sprint 38 — same
    reasoning: a real DB-level guarantee of deterministic section
    order within one test, not just an advisory sort hint."""
    __tablename__ = "exam_sections"
    __table_args__ = (UniqueConstraint("test_id", "order_number", name="uq_exam_sections_test_id_order_number"),)

    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tests.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Optional section-level timing, independent of Test.duration
    # (which remains the whole-test timer attempts/service.py already
    # uses — unchanged). NULL means this section has no timing of its
    # own; nothing in this sprint enforces it yet (foundation only,
    # per this sprint's explicit scope).
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
