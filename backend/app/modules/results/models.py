"""
Result, Statistics, Ranking ORM models — mirror `results`, `statistics`,
`ranking` tables in schema_v2.sql (Module 16). `badges`/`achievements`
(also Module 16) are deliberately NOT modeled here — deferred per
docs/Sprint7_Results_Certificates_Analytics_Architecture.md Future
Extensions.

None of the three tables have created_by/updated_by (verified against
schema_v2.sql) — no AuditMixin, same situation as the attempts module.
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class Result(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "results"

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tests.id"), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    is_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="final")


class Statistics(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "statistics"
    # Sprint 69 (F1) — was previously unconstrained (no unique
    # constraint existed at all against the live schema, confirmed
    # during the Sprint 69 audit), letting ResultService.
    # _update_statistics()'s check-then-act read/create-or-update race
    # produce duplicate rows for the same (user_id, subject_id) under
    # concurrent writes. NULLS NOT DISTINCT so subject_id IS NULL (the
    # "overall, not subject-scoped" bucket) participates in uniqueness
    # exactly like a real subject UUID, matching StatisticsRepository
    # .upsert()'s ON CONFLICT target — see migration 0016.
    __table_args__ = (UniqueConstraint("user_id", "subject_id", name="uq_statistics_user_id_subject_id", postgresql_nulls_not_distinct=True),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    tests_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wrong_answers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class Ranking(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ranking"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    period: Mapped[str] = mapped_column(String(20), nullable=False, default="all_time")
    score: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class ResultSection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Sprint 47 — IELTS Engine foundation. Generic, additive
    section-level score storage under a Result — deliberately NOT
    IELTS-specific columns (no listening_score/reading_score/
    writing_score/speaking_score). One row per (result, section).

    Existing Result.score/.percentage/.is_passed are completely
    unchanged. Nothing in this sprint creates a ResultSection
    automatically; a Result with zero ResultSection rows (every
    existing result) behaves exactly as before this table existed."""
    __tablename__ = "result_sections"
    __table_args__ = (UniqueConstraint("result_id", "section_id", name="uq_result_sections_result_id_section_id"),)

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("results.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_sections.id", ondelete="CASCADE"), nullable=False)
    raw_score: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    scaled_score: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
