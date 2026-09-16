"""Sprint 46 — Generic Exam Module Foundation

Fully additive. Nothing existing is altered, dropped, or renamed.
Every new column is nullable (or has a safe, backward-compatible
default) with no server_default that changes existing row semantics —
every current Physics/National Certificate test, question, and attempt
continues to behave EXACTLY as before this migration.

1. exam_modules (new table)
   Second hierarchy level under exam_sections (Sprint 45's own audit
   finding: a Section alone cannot represent SAT's two-module
   structure within "Reading and Writing" / "Math"). A Section with
   zero modules (every existing ExamSection) is unaffected.
   Mirrors exam_sections' own shape exactly, including the
   UNIQUE(section_id, order_number) guarantee Sprint 38/45 already
   established the reasoning for. difficulty_tier is a nullable
   foundation placeholder only — no routing logic reads it yet.

   IMPORTANT: this model inherits TimestampMixin (created_at,
   updated_at, deleted_at) — Sprint 40 and Sprint 45 both exposed a
   real bug where a TimestampMixin model's migration omitted
   deleted_at. deleted_at IS included here from the start.

2. questions.module_id (nullable FK -> exam_modules.id, SET NULL)
   NULL for every existing question (unchanged). questions.test_id and
   questions.section_id are completely untouched — test_id remains
   the mandatory ownership FK it has always been; this migration does
   not make it nullable and does not implement question-bank reuse.

3. attempt_module_progress (new table)
   One row per (attempt, module) — a single attempt's progress through
   one ExamModule. Nothing creates a row here automatically; an
   attempt against a moduleless test (every existing attempt) simply
   never has any rows here, exactly as before this table existed.
   question_order reuses test_attempts.question_order's own
   established ARRAY-of-UUID, persist-not-compute pattern (Sprint 2's
   original reasoning) rather than a new association table — see the
   Sprint 46 revision audit's point 2 for why no
   attempt_module_questions table was introduced.
   Also inherits TimestampMixin — deleted_at is included here too.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("order_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("difficulty_tier", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("section_id", "order_number", name="uq_exam_modules_section_id_order_number"),
    )
    op.alter_column("exam_modules", "order_number", server_default=None)
    op.create_index("ix_exam_modules_section_id", "exam_modules", ["section_id"])

    op.add_column(
        "questions",
        sa.Column("module_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_modules.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_questions_module_id", "questions", ["module_id"])

    op.create_table(
        "attempt_module_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("question_order", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("attempt_id", "module_id", name="uq_attempt_module_progress_attempt_id_module_id"),
    )
    op.alter_column("attempt_module_progress", "status", server_default=None)
    op.create_index("ix_attempt_module_progress_attempt_id", "attempt_module_progress", ["attempt_id"])
    op.create_index("ix_attempt_module_progress_module_id", "attempt_module_progress", ["module_id"])


def downgrade() -> None:
    op.drop_index("ix_attempt_module_progress_module_id", table_name="attempt_module_progress")
    op.drop_index("ix_attempt_module_progress_attempt_id", table_name="attempt_module_progress")
    op.drop_table("attempt_module_progress")

    op.drop_index("ix_questions_module_id", table_name="questions")
    op.drop_column("questions", "module_id")

    op.drop_index("ix_exam_modules_section_id", table_name="exam_modules")
    op.drop_table("exam_modules")
