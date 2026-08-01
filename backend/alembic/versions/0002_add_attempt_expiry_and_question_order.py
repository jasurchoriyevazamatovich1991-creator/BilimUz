"""Add expires_at and question_order to test_attempts

Sprint 6 (Test Engine) architecture decision: persist the attempt's
expiry timestamp and randomized question order at start-time, instead of
computing them on every request. See docs/Sprint6_TestEngine_Architecture.md
sections 3, 7, 8 for the full design rationale — this migration
implements the "store, don't compute" option that was chosen over the
zero-migration alternative.

- expires_at: snapshotted as `start_time + tests.duration` the instant
  an attempt starts. Storing it (rather than recomputing from tests.duration
  on every check) means an Admin editing a test's duration mid-exam can
  never retroactively change the deadline for attempts already in progress
  — closes the fairness gap flagged in the architecture doc's Section 7.
- question_order: the randomized (or non-randomized, if shuffle_questions
  is false) list of question IDs, snapshotted once at start. Makes every
  attempt fully reproducible for resume, audit, and future analytics —
  no seeded-PRNG reconstruction needed at read time.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_attempts",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "test_attempts",
        sa.Column(
            "question_order",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_test_attempts_expires_at", "test_attempts", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_test_attempts_expires_at", table_name="test_attempts")
    op.drop_column("test_attempts", "question_order")
    op.drop_column("test_attempts", "expires_at")
