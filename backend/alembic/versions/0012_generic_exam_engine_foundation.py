"""Sprint 45 — Generic Exam Engine Foundation

Fully additive migration. Nothing existing is altered, dropped, or
renamed. Every new column is nullable with no server_default that
changes existing row semantics, so every current Physics/National
Certificate test, question, and answer continues to behave EXACTLY as
before this migration.

1. tests.max_attempts (Integer, nullable)
   NULL means "use the platform default" (DEFAULT_MAX_ATTEMPTS = 1,
   attempts/constants.py — unchanged). This is how max_attempts comes
   out of hardcoding: existing tests (all currently NULL) keep their
   exact current behavior; a Test can now opt into a different limit
   without any code change.

2. answers.text_answer (Text, nullable)
   Foundation for free-text responses (short_answer/essay question
   types already exist in QuestionType but have never had anywhere to
   store a text response — verified directly against
   app/modules/attempts/models.py's Answer model, which only ever had
   selected_option/selected_options). NULL for every existing answer
   and for every answer to a choice-based question — this sprint adds
   the storage column only; scoring/grading of free-text answers is
   explicitly out of scope (see Sprint 45 prompt's item 14/15).

3. exam_sections (new table)
   Optional grouping of Questions within a Test — e.g. SAT's
   "Reading and Writing" / "Math", IELTS's "Listening" / "Reading" /
   "Writing" / "Speaking". A Test with no sections (every existing
   Physics/National Certificate test) behaves identically: its
   Questions simply have section_id = NULL, exactly as before this
   migration existed.
   - id, test_id (FK -> tests.id, CASCADE — a section cannot outlive
     its test), name, order_number (mirrors the existing, proven
     Topic.order_number / Lesson.order_number pattern from Sprint 38),
     duration (nullable Integer — optional section-level timing,
     independent of Test.duration), created_at/updated_at.
   - UNIQUE(test_id, order_number) — same deterministic-ordering
     guarantee Sprint 38 established for Lesson.order_number.

4. questions.section_id (nullable FK -> exam_sections.id, SET NULL)
   NULL for every existing question (unchanged). A question is
   optionally scoped to one section of its test.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tests", sa.Column("max_attempts", sa.Integer(), nullable=True))
    op.add_column("answers", sa.Column("text_answer", sa.Text(), nullable=True))

    op.create_table(
        "exam_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("order_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # TimestampMixin (app/core/mixins.py) also defines deleted_at —
        # discovered missing here during Sprint 45's own final
        # verification (the exact same class of model/migration
        # mismatch Sprint 40 found and fixed for LessonProgress).
        # Included from the start this time rather than a follow-up
        # migration, since 0012 had not yet been pushed.
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("test_id", "order_number", name="uq_exam_sections_test_id_order_number"),
    )
    op.alter_column("exam_sections", "order_number", server_default=None)

    op.add_column(
        "questions",
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_sections.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_questions_section_id", "questions", ["section_id"])


def downgrade() -> None:
    op.drop_index("ix_questions_section_id", table_name="questions")
    op.drop_column("questions", "section_id")
    op.drop_table("exam_sections")
    op.drop_column("answers", "text_answer")
    op.drop_column("tests", "max_attempts")
