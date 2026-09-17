"""Sprint 48 — Generic Adaptive Routing Foundation

Fully additive. Nothing existing is altered, dropped, or renamed.
Every new column is nullable — every current Physics/National
Certificate/Sprint 45-47 test, question, and result continues to
behave EXACTLY as before this migration.

1. question_groups.module_id (nullable FK -> exam_modules.id, SET NULL)
   NULL for every existing QuestionGroup (unchanged). Optional
   DB-level scoping of a group to a specific ExamModule — a group that
   operates at section level without a module (e.g. an IELTS Reading
   passage) is unaffected.

2. exam_modules.routing_group (nullable String(50))
   exam_modules.routing_variant (nullable String(50))
   Generic metadata only — no routing DECISION logic reads these yet.
   NULL for every existing module. No SAT/GRE-specific values are
   hardcoded anywhere in production code.

No new tables — the Sprint 48 audit determined that
AttemptModuleProgress (Sprint 46) already provides sufficient
assignment/snapshot state (attempt_id, module_id, status,
question_order, expires_at, submitted_at); a separate module
assignment or question-assignment table was judged unnecessary and
was deliberately not created here.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "question_groups",
        sa.Column("module_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_modules.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_question_groups_module_id", "question_groups", ["module_id"])

    op.add_column("exam_modules", sa.Column("routing_group", sa.String(50), nullable=True))
    op.add_column("exam_modules", sa.Column("routing_variant", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("exam_modules", "routing_variant")
    op.drop_column("exam_modules", "routing_group")

    op.drop_index("ix_question_groups_module_id", table_name="question_groups")
    op.drop_column("question_groups", "module_id")
