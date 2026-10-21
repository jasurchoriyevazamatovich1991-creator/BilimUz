"""Task 5 — manual grading workflow (IELTS Writing/Speaking, GRE AWA).

Additive:
- grading_rubrics   versioned, immutable admin-defined rubrics per manual
                    component (no official rubric data is inserted)
- manual_reviews    append-only grading history per (attempt, question):
                    drafts, finalized reviews, superseded revisions
- results.is_provisional, result_sections.is_provisional
- permission GRADE_SUBMISSIONS, granted to Admin and Super Admin only
  (other roles must be granted it explicitly via Roles/Permissions)

Downgrade removes exactly these objects (and the permission grant).

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "grading_rubrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("score_component", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("criteria", postgresql.JSONB(), nullable=False),
        sa.Column("rounding", sa.String(20), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("is_validated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("score_component IN ('ielts_writing', 'ielts_speaking', 'gre_analytical_writing')", name="ck_grading_rubrics_component"),
        sa.CheckConstraint("rounding IN ('half_up', 'floor')", name="ck_grading_rubrics_rounding"),
        sa.CheckConstraint("version >= 1", name="ck_grading_rubrics_version_positive"),
    )
    op.create_index("uq_grading_rubrics_component_version", "grading_rubrics", ["score_component", "version"], unique=True)

    op.create_table(
        "manual_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rubric_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grading_rubrics.id"), nullable=False),
        sa.Column("grader_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("criterion_scores", postgresql.JSONB(), nullable=False),
        sa.Column("criterion_total", sa.Numeric(8, 2), nullable=True),
        sa.Column("reported_score", sa.Numeric(4, 1), nullable=True),
        sa.Column("is_provisional", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("manual_reviews.id"), nullable=True),
        sa.Column("revision_reason", sa.Text(), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('draft', 'finalized', 'superseded')", name="ck_manual_reviews_status"),
        sa.CheckConstraint("revision_number >= 1", name="ck_manual_reviews_revision_positive"),
        sa.CheckConstraint("status = 'draft' OR (finalized_at IS NOT NULL AND reported_score IS NOT NULL)", name="ck_manual_reviews_finalized_complete"),
    )
    op.create_index("ix_manual_reviews_attempt", "manual_reviews", ["attempt_id"])
    op.create_index("uq_manual_reviews_one_draft", "manual_reviews", ["attempt_id", "question_id"], unique=True,
                    postgresql_where=sa.text("status = 'draft' AND deleted_at IS NULL"))
    op.create_index("uq_manual_reviews_one_finalized", "manual_reviews", ["attempt_id", "question_id"], unique=True,
                    postgresql_where=sa.text("status = 'finalized' AND deleted_at IS NULL"))

    op.add_column("results", sa.Column("is_provisional", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("result_sections", sa.Column("is_provisional", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    op.execute(
        "INSERT INTO permissions (name, code, module, description) "
        "SELECT 'Imtihon javoblarini baholash', 'GRADE_SUBMISSIONS', 'grading', "
        "'IELTS Writing/Speaking va GRE AWA javoblarini ko''rish va baholash' "
        "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'GRADE_SUBMISSIONS')"
    )
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id) "
        "SELECT r.id, p.id FROM roles r, permissions p "
        "WHERE r.name IN ('Admin', 'Super Admin') AND p.code = 'GRADE_SUBMISSIONS' "
        "AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'GRADE_SUBMISSIONS')"
    )
    op.execute("DELETE FROM permissions WHERE code = 'GRADE_SUBMISSIONS'")
    op.drop_column("result_sections", "is_provisional")
    op.drop_column("results", "is_provisional")
    op.drop_index("uq_manual_reviews_one_finalized", table_name="manual_reviews")
    op.drop_index("uq_manual_reviews_one_draft", table_name="manual_reviews")
    op.drop_index("ix_manual_reviews_attempt", table_name="manual_reviews")
    op.drop_table("manual_reviews")
    op.drop_index("uq_grading_rubrics_component_version", table_name="grading_rubrics")
    op.drop_table("grading_rubrics")
