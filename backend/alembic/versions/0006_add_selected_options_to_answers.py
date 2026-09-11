"""Add selected_options to answers for multiple_choice support (Sprint 30)

Approved architecture: purely ADDITIVE. `answers.selected_option`
(singular, existing since Sprint 6) is completely unchanged and keeps
serving single_choice/true_false exactly as before — no existing data
is touched, no column is renamed or dropped. A new nullable
`selected_options` (plural, PostgreSQL ARRAY(UUID)) column is added
specifically for multiple_choice questions.

ARRAY(UUID) is not a new pattern in this schema — `test_attempts.
question_order` (migration 0002) already uses the exact same type for
persisting an ordered list of UUIDs, so this follows established,
already-working precedent rather than introducing something new.

Nullable: every existing answer row (single_choice/true_false, or any
multiple_choice answer saved before this sprint) has NULL here and
continues to be read/scored via the existing `selected_option` column
untouched — full backward compatibility, no data migration required.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "answers",
        sa.Column("selected_options", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("answers", "selected_options")
