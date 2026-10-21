"""Task 4 — exam-specific scaled scoring (IELTS, SAT, GRE).

Fully additive; every existing row keeps NULL in the new columns, which
means "plain percentage scoring" — the exact pre-0025 behavior.

- tests.scoring_profile           'ielts' | 'sat' | 'gre' | NULL (CHECK)
- exam_sections.score_component   which exam component a section is (CHECK),
                                  unique per test among active sections
- score_conversion_tables (new)   admin-managed, versioned, immutable
                                  raw->scaled mappings per section (= exam
                                  component of one test form), optionally
                                  per adaptive routing_variant
- results.scoring_profile / overall_scaled_score / overall_status
- result_sections.score_component / scaled_status / conversion_table_id
  (the exact table version used, for reproducibility)

No official conversion data is inserted.

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COMPONENT_CHECK = (
    "score_component IS NULL OR score_component IN ("
    "'ielts_listening', 'ielts_reading', 'ielts_writing', 'ielts_speaking', "
    "'sat_reading_writing', 'sat_math', "
    "'gre_verbal', 'gre_quantitative', 'gre_analytical_writing')"
)


def upgrade() -> None:
    op.add_column("tests", sa.Column("scoring_profile", sa.String(20), nullable=True))
    op.create_check_constraint(
        "ck_tests_scoring_profile_allowed", "tests",
        "scoring_profile IS NULL OR scoring_profile IN ('ielts', 'sat', 'gre')",
    )

    op.add_column("exam_sections", sa.Column("score_component", sa.String(40), nullable=True))
    op.create_check_constraint("ck_exam_sections_score_component_allowed", "exam_sections", COMPONENT_CHECK)
    op.create_index(
        "uq_exam_sections_active_test_score_component", "exam_sections", ["test_id", "score_component"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL AND score_component IS NOT NULL"),
    )

    op.create_table(
        "score_conversion_tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("routing_variant", sa.String(50), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("entries", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("method IN ('exact', 'linear')", name="ck_score_conversion_tables_method"),
        sa.CheckConstraint("version >= 1", name="ck_score_conversion_tables_version_positive"),
    )
    op.create_index("ix_score_conversion_tables_section_id", "score_conversion_tables", ["section_id"])
    op.create_index(
        "uq_score_conversion_tables_section_variant_version", "score_conversion_tables",
        ["section_id", sa.text("COALESCE(routing_variant, '')"), "version"], unique=True,
    )

    op.add_column("results", sa.Column("scoring_profile", sa.String(20), nullable=True))
    op.add_column("results", sa.Column("overall_scaled_score", sa.Numeric(6, 1), nullable=True))
    op.add_column("results", sa.Column("overall_status", sa.String(30), nullable=True))

    op.add_column("result_sections", sa.Column("score_component", sa.String(40), nullable=True))
    op.add_column("result_sections", sa.Column("scaled_status", sa.String(30), nullable=True))
    op.add_column(
        "result_sections",
        sa.Column("conversion_table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("score_conversion_tables.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("result_sections", "conversion_table_id")
    op.drop_column("result_sections", "scaled_status")
    op.drop_column("result_sections", "score_component")
    op.drop_column("results", "overall_status")
    op.drop_column("results", "overall_scaled_score")
    op.drop_column("results", "scoring_profile")
    op.drop_index("uq_score_conversion_tables_section_variant_version", table_name="score_conversion_tables")
    op.drop_index("ix_score_conversion_tables_section_id", table_name="score_conversion_tables")
    op.drop_table("score_conversion_tables")
    op.drop_index("uq_exam_sections_active_test_score_component", table_name="exam_sections")
    op.drop_constraint("ck_exam_sections_score_component_allowed", "exam_sections", type_="check")
    op.drop_column("exam_sections", "score_component")
    op.drop_constraint("ck_tests_scoring_profile_allowed", "tests", type_="check")
    op.drop_column("tests", "scoring_profile")
