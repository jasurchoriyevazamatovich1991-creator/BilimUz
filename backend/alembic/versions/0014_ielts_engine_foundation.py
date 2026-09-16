"""Sprint 47 — IELTS Engine Foundation

Fully additive. Nothing existing is altered, dropped, or renamed.
Every new column is nullable — every current Physics/National
Certificate/SAT-foundation test, question, and result continues to
behave EXACTLY as before this migration.

1. question_groups (new table)
   Generic shared-stimulus foundation (deliberately NOT an
   IELTS-specific "Passage" model) — e.g. an IELTS Reading passage or
   Listening audio, or a future SAT shared Reading & Writing passage.
   Mirrors exam_sections' own proven shape, including
   UNIQUE(test_id, order_number). Inherits TimestampMixin — deleted_at
   is included from the start (Sprint 40/45/46 all previously exposed
   this exact class of bug when it was omitted).

2. questions.group_id (nullable FK -> question_groups.id, SET NULL)
   NULL for every existing question (unchanged). questions.test_id,
   .section_id, .module_id are completely untouched.

3. tests.exam_variant (nullable String(50))
   Generic — no IELTS-specific enum or CHECK constraint. NULL for
   every existing test.

4. result_sections (new table)
   Generic, additive section-level score storage under a Result — NOT
   IELTS-specific columns (no listening_score/reading_score/etc.).
   UNIQUE(result_id, section_id). Inherits TimestampMixin — deleted_at
   included from the start.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "question_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("stimulus_text", sa.Text(), nullable=True),
        sa.Column("order_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("test_id", "order_number", name="uq_question_groups_test_id_order_number"),
    )
    op.alter_column("question_groups", "order_number", server_default=None)
    op.create_index("ix_question_groups_test_id", "question_groups", ["test_id"])

    op.add_column(
        "questions",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("question_groups.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_questions_group_id", "questions", ["group_id"])

    op.add_column("tests", sa.Column("exam_variant", sa.String(50), nullable=True))

    op.create_table(
        "result_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_score", sa.Numeric(8, 2), nullable=True),
        sa.Column("scaled_score", sa.Numeric(8, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("result_id", "section_id", name="uq_result_sections_result_id_section_id"),
    )
    op.create_index("ix_result_sections_result_id", "result_sections", ["result_id"])
    op.create_index("ix_result_sections_section_id", "result_sections", ["section_id"])


def downgrade() -> None:
    op.drop_index("ix_result_sections_section_id", table_name="result_sections")
    op.drop_index("ix_result_sections_result_id", table_name="result_sections")
    op.drop_table("result_sections")

    op.drop_column("tests", "exam_variant")

    op.drop_index("ix_questions_group_id", table_name="questions")
    op.drop_column("questions", "group_id")

    op.drop_index("ix_question_groups_test_id", table_name="question_groups")
    op.drop_table("question_groups")
