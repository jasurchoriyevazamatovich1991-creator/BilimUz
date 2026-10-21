"""
Task 5 — manual grading ORM models.

GradingRubric: admin-defined, versioned, immutable rubric for one manually
graded exam component (IELTS Writing, IELTS Speaking, GRE Analytical
Writing). A change is a new version; reviews keep the exact version used.

ManualReview: one grader's assessment of one delivered question of one
finished attempt. Keyed by (attempt_id, question_id) rather than by an
Answer row, so a question the student left blank can still be graded.
History is append-only: a correction is a NEW review row (revision_number
+ 1, supersedes_id -> previous) and the previous finalized row becomes
'superseded' — nothing is overwritten.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class GradingRubric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "grading_rubrics"
    __table_args__ = (
        CheckConstraint(
            "score_component IN ('ielts_writing', 'ielts_speaking', 'gre_analytical_writing')",
            name="ck_grading_rubrics_component",
        ),
        CheckConstraint("rounding IN ('half_up', 'floor')", name="ck_grading_rubrics_rounding"),
        CheckConstraint("version >= 1", name="ck_grading_rubrics_version_positive"),
        Index("uq_grading_rubrics_component_version", "score_component", "version", unique=True),
    )

    score_component: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    # [{key, label, min, max, step, weight}] — validated, canonical strings.
    criteria: Mapped[list] = mapped_column(JSONB, nullable=False)
    rounding: Mapped[str] = mapped_column(String(20), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # False = not confirmed against a validated official source; every score
    # produced with this version is marked provisional.
    is_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class ManualReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "manual_reviews"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'finalized', 'superseded')", name="ck_manual_reviews_status"),
        CheckConstraint("revision_number >= 1", name="ck_manual_reviews_revision_positive"),
        CheckConstraint(
            "status = 'draft' OR (finalized_at IS NOT NULL AND reported_score IS NOT NULL)",
            name="ck_manual_reviews_finalized_complete",
        ),
        # At most one open draft and one current finalized review per item.
        Index("uq_manual_reviews_one_draft", "attempt_id", "question_id", unique=True,
              postgresql_where=text("status = 'draft' AND deleted_at IS NULL")),
        Index("uq_manual_reviews_one_finalized", "attempt_id", "question_id", unique=True,
              postgresql_where=text("status = 'finalized' AND deleted_at IS NULL")),
        Index("ix_manual_reviews_attempt", "attempt_id"),
    )

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_sections.id", ondelete="CASCADE"), nullable=False)
    rubric_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grading_rubrics.id"), nullable=False)
    grader_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    criterion_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    criterion_total: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    reported_score: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    # Snapshot of "rubric not validated" at finalization time.
    is_provisional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)        # shown to the student
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # graders/admins only
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("manual_reviews.id"), nullable=True)
    revision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
