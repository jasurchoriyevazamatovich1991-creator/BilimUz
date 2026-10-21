"""Test ORM model — mirrors `tests` table in schema_v2.sql (Module 11).
Test *definition* only — the taking-experience lives in the `attempts`
module, which reads this model read-only."""
import uuid
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


# Task 4 — mirrors results/scaled_scoring.COMPONENTS (kept literal here so
# the model module has no dependency on the results module).
SCORE_COMPONENT_CHECK_SQL = (
    "score_component IS NULL OR score_component IN ("
    "'ielts_listening', 'ielts_reading', 'ielts_writing', 'ielts_speaking', "
    "'sat_reading_writing', 'sat_math', "
    "'gre_verbal', 'gre_quantitative', 'gre_analytical_writing')"
)


class Test(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin):
    __tablename__ = "tests"
    __table_args__ = (
        # Migration 0021 — "Mock Test" entitlement feature. A test
        # flagged as a mock test MUST carry a subject_id, because
        # subject_id is what the entitlements module keys the
        # subject/exam-direction access check on (see
        # entitlements/repository.py's has_active_mock_test_entitlement).
        # Every pre-existing row defaults is_mock_test=False, so no
        # existing test is retroactively (and possibly wrongly)
        # categorized as a mock test by this migration — see
        # migration 0021's own docstring and tests/README.md.
        CheckConstraint(
            "is_mock_test = false OR subject_id IS NOT NULL",
            name="ck_tests_mock_test_requires_subject",
        ),
        CheckConstraint(
            "scoring_profile IS NULL OR scoring_profile IN ('ielts', 'sat', 'gre')",
            name="ck_tests_scoring_profile_allowed",
        ),
    )

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
    # Sprint 47 — additive, generic. NULL for every existing test
    # (unchanged). Deliberately a plain nullable string, not an enum —
    # no IELTS-specific values ("Academic"/"General Training") are
    # hardcoded anywhere in production code; this field only carries
    # whatever value a caller assigns it.
    exam_variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Migration 0021 — "Mock Test" entitlement feature (subject/exam-
    # direction access, not a single-test unlock). False for every
    # existing test (the DB default) — a pre-existing test is never
    # silently reinterpreted as a mock test by this migration; an
    # admin must explicitly opt a test into this category, and doing
    # so requires subject_id to already be set (see the CHECK
    # constraint above and TestService._validate_mock_test_consistency()).
    is_mock_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Task 4 (migration 0025) — explicit exam scoring profile: 'ielts',
    # 'sat', 'gre', or NULL. NULL (every existing test) keeps the plain
    # percentage scoring, unchanged. Set only by Admin/Super Admin via
    # PUT /tests/{id}/scoring-profile; never inferred from the title.
    scoring_profile: Mapped[str | None] = mapped_column(String(20), nullable=True)


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
    __table_args__ = (
        UniqueConstraint("test_id", "order_number", name="uq_exam_sections_test_id_order_number"),
        CheckConstraint(SCORE_COMPONENT_CHECK_SQL, name="ck_exam_sections_score_component_allowed"),
        Index(
            "uq_exam_sections_active_test_score_component", "test_id", "score_component",
            unique=True, postgresql_where=text("deleted_at IS NULL AND score_component IS NOT NULL"),
        ),
    )

    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tests.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Optional section-level timing, independent of Test.duration
    # (which remains the whole-test timer attempts/service.py already
    # uses — unchanged). NULL means this section has no timing of its
    # own; nothing in this sprint enforces it yet (foundation only,
    # per this sprint's explicit scope).
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Task 4 (migration 0025) — which scored exam component this section
    # is (e.g. 'sat_math', 'ielts_listening'); see
    # results/scaled_scoring.COMPONENTS. Must match the test's
    # scoring_profile; unique among a test's active sections.
    score_component: Mapped[str | None] = mapped_column(String(40), nullable=True)


class ExamModule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Sprint 46 — Generic Exam Module foundation. Optional second
    hierarchy level under ExamSection (Sprint 45's audit finding: a
    Section alone cannot represent SAT's two-module structure inside
    "Reading and Writing" / "Math"). A Section with zero modules
    (every ExamSection created before this sprint, and any exam that
    doesn't need module-level structure — e.g. plain IELTS sections)
    is completely unaffected.

    Mirrors ExamSection's own pattern exactly (same UNIQUE(parent,
    order_number) guarantee, same TimestampMixin usage) — this sprint
    deliberately adds no SAT-specific fields beyond the one nullable
    difficulty_tier the approved scope explicitly asked for as a
    foundation placeholder; no routing/adaptive logic reads it yet."""
    __tablename__ = "exam_modules"
    __table_args__ = (UniqueConstraint("section_id", "order_number", name="uq_exam_modules_section_id_order_number"),)

    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_sections.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Foundation placeholder only (Sprint 46 audit item 3) — no
    # adaptive routing logic reads or writes this yet. A future
    # "SAT Adaptive Implementation" sprint would use this (plus a
    # separate routing-rule concept) to decide which Module 2 variant
    # an attempt is routed to.
    difficulty_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Sprint 48 — additive, generic metadata only. NULL for every
    # existing module (unchanged). No routing DECISION logic reads
    # these yet (out of scope — see AdaptiveRoutingStrategy in
    # attempts/adaptive_routing.py) — they only let a future routing
    # strategy identify "which modules are alternatives for the same
    # position" (routing_group) and "which specific alternative this
    # is" (routing_variant). No SAT/GRE-specific values are hardcoded
    # anywhere in production code; these fields only carry whatever a
    # caller assigns them.
    routing_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    routing_variant: Mapped[str | None] = mapped_column(String(50), nullable=True)


class QuestionGroup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Sprint 47 — IELTS Engine foundation, deliberately generic (not an
    IELTS-specific "Passage" model). Represents a shared stimulus a set
    of Questions is grouped under — e.g. an IELTS Reading passage or
    Listening audio, or a future SAT shared Reading & Writing passage.
    A question that doesn't use groups (every existing question) is
    completely unaffected — group_id stays NULL, exactly as before
    this table existed.

    Always scoped to exactly one Test (mandatory test_id) — mirrors
    ExamSection's own ownership pattern exactly, including the same
    UNIQUE(test_id, order_number) deterministic-ordering guarantee."""
    __tablename__ = "question_groups"
    __table_args__ = (UniqueConstraint("test_id", "order_number", name="uq_question_groups_test_id_order_number"),)

    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tests.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    stimulus_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Sprint 48 — additive. NULL for every existing QuestionGroup
    # (unchanged) — a group that operates at section level without a
    # module (e.g. an IELTS Reading passage with no module concept)
    # stays exactly as before. Optional DB-level scoping to a specific
    # ExamModule, so a group's questions can be unambiguously tied to
    # one module when adaptive module structure is in use — SET NULL
    # on module delete, matching Question.module_id/.section_id/
    # .group_id's own established pattern.
    module_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_modules.id", ondelete="SET NULL"), nullable=True)

    # Task 3 — read-only view of this group's NON-deleted media, in attach
    # order. viewonly: rows are only ever written through
    # QuestionGroupMediaRepository.
    media: Mapped[list["QuestionGroupMedia"]] = relationship(
        "QuestionGroupMedia",
        primaryjoin="and_(QuestionGroup.id == QuestionGroupMedia.group_id, QuestionGroupMedia.deleted_at.is_(None))",
        order_by="(QuestionGroupMedia.created_at, QuestionGroupMedia.id)",
        viewonly=True,
        lazy="selectin",
    )


class QuestionGroupMedia(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin):
    """Task 3 (migration 0024) — media attached to a QuestionGroup as a
    whole, e.g. the audio of an IELTS Listening section shared by all of
    its questions.

    Always backed by a real Upload row (upload_id NOT NULL): no file_url
    copy is stored, so there is no second, possibly stale, location field
    and no unauthenticated external-URL path. media_type is derived from
    the Upload's own backend-classified file_type when the row is
    created (never client-supplied), and is limited to audio/image.

    A soft-deleted row (deleted_at set) is never delivered; the partial
    unique index stops the same upload being attached to the same group
    twice while still allowing it to be re-attached after removal."""
    __tablename__ = "question_group_media"
    __table_args__ = (
        CheckConstraint("media_type IN ('audio', 'image')", name="ck_question_group_media_type_allowed"),
        Index(
            "uq_question_group_media_active_group_upload", "group_id", "upload_id",
            unique=True, postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("question_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)


class RoutingThresholdRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Sprint 75 — Live Adaptive Routing Engine: the persistent
    configuration `PerformanceThresholdRoutingStrategy`
    (attempts/adaptive_routing.py, Sprint 49) has needed since it was
    written but never had a real source for in production (see
    migration 0019's docstring for the full Phase 3 reasoning on why
    this is a genuine new table, not something derivable from existing
    ExamModule columns).

    Always scoped to exactly one Test (mandatory test_id) — mirrors
    ExamSection/QuestionGroup's own ownership pattern. A rule only ever
    applies to modules belonging to the SAME test as this row's test_id
    (enforced by RoutingThresholdRuleRepository's only reader method,
    which filters by test_id), so a routing_group name reused across
    two different tests can never cross-apply.

    One row = one (routing_group, min_ratio -> variant) rule, mirroring
    adaptive_routing.PerformanceThresholdRule's own two fields exactly
    — this table is that dataclass's persistence, nothing more.

    No admin UI/endpoint creates these rows in Sprint 75 (explicitly
    deferred — see README). Every pre-existing exam therefore has zero
    rows here, which is what keeps Sprint 75 fully backward-compatible:
    see ModuleExecutionService._select_routing_strategy()."""
    __tablename__ = "routing_threshold_rules"
    __table_args__ = (
        UniqueConstraint("test_id", "routing_group", "min_ratio", name="uq_routing_threshold_rules_test_group_ratio"),
    )

    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tests.id", ondelete="CASCADE"), nullable=False)
    routing_group: Mapped[str] = mapped_column(String(50), nullable=False)
    min_ratio: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    variant: Mapped[str] = mapped_column(String(50), nullable=False)


class ScoreConversionTable(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin):
    """Task 4 (migration 0025) — an admin-managed raw-to-scaled mapping for
    one ExamSection (= one exam component of one test form), optionally
    for one adaptive routing_variant of that section.

    Rows are immutable once created: "changing" a table publishes a new
    version (version + 1 for the same section/variant). The current table
    is the highest active version. ResultSection.conversion_table_id
    records exactly which row produced a scaled score, so results stay
    reproducible after later updates. entries holds the validated,
    canonical [{"raw": "12", "scaled": "650"}, ...] list
    (results/scaled_scoring.validate_conversion_table)."""
    __tablename__ = "score_conversion_tables"
    __table_args__ = (
        CheckConstraint("method IN ('exact', 'linear')", name="ck_score_conversion_tables_method"),
        CheckConstraint("version >= 1", name="ck_score_conversion_tables_version_positive"),
        Index(
            "uq_score_conversion_tables_section_variant_version", "section_id",
            text("COALESCE(routing_variant, '')"), "version", unique=True,
        ),
    )

    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_sections.id", ondelete="CASCADE"), nullable=False, index=True)
    routing_variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    entries: Mapped[list] = mapped_column(JSONB, nullable=False)
