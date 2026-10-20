"""Task 2 — automatic grading configuration for short_answer questions
(IELTS gap-fill, SAT grid-in, GRE numeric entry).

Fully additive. Four new columns on `questions`, all NULL/false for every
existing row, which keeps every existing question exactly as it is today:
short_answer/essay stay ungraded (manual review) unless an admin
explicitly configures answer_format + accepted_answers.

- answer_format      VARCHAR(20) NULL  — 'text' | 'numeric' | NULL
- accepted_answers   TEXT[]      NULL  — one or more accepted answers
- case_sensitive     BOOLEAN NOT NULL DEFAULT false — text format only
- numeric_tolerance  NUMERIC(20,10) NULL — numeric format only, >= 0

CHECK constraints keep the configuration coherent even for writes that
bypass the service layer. No existing column, constraint or row value is
touched; the downgrade drops exactly what this revision adds.

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("answer_format", sa.String(20), nullable=True))
    op.add_column("questions", sa.Column("accepted_answers", postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column(
        "questions",
        sa.Column("case_sensitive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("questions", sa.Column("numeric_tolerance", sa.Numeric(20, 10), nullable=True))

    op.create_check_constraint(
        "ck_questions_answer_format_allowed",
        "questions",
        "answer_format IS NULL OR answer_format IN ('text', 'numeric')",
    )
    op.create_check_constraint(
        "ck_questions_answer_format_short_answer_only",
        "questions",
        "answer_format IS NULL OR question_type = 'short_answer'",
    )
    op.create_check_constraint(
        "ck_questions_numeric_tolerance_numeric_only",
        "questions",
        "numeric_tolerance IS NULL OR (answer_format = 'numeric' AND numeric_tolerance >= 0)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_questions_numeric_tolerance_numeric_only", "questions", type_="check")
    op.drop_constraint("ck_questions_answer_format_short_answer_only", "questions", type_="check")
    op.drop_constraint("ck_questions_answer_format_allowed", "questions", type_="check")
    op.drop_column("questions", "numeric_tolerance")
    op.drop_column("questions", "case_sensitive")
    op.drop_column("questions", "accepted_answers")
    op.drop_column("questions", "answer_format")
