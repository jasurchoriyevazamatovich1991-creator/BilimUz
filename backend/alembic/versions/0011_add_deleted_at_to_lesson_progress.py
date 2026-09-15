"""Add deleted_at to lesson_progress — fixes a model/migration mismatch (Sprint 40)

BUG FOUND DURING SPRINT 40 INTEGRATION TESTING (real PostgreSQL, not
mock-based tests): `LessonProgress` (app/modules/progress/models.py)
inherits `TimestampMixin`, which defines THREE columns —
`created_at`, `updated_at`, AND `deleted_at` (see app/core/mixins.py).
Migration 0009 (Sprint 36) only created `created_at`/`updated_at` for
the `lesson_progress` table, omitting `deleted_at` — an oversight that
every existing mock-based test (MagicMock repositories, no real SQL)
was structurally unable to catch, since it never generates a real
SELECT against the real table.

This migration is purely additive: it adds the ONE missing column so
the table matches what the model has always declared. No other column,
table, or existing migration is touched. `lesson_progress.user_id`,
`.lesson_id`, `.completed_at`, `.created_at`, `.updated_at`, and the
UNIQUE(user_id, lesson_id) constraint from migration 0009 are all
completely unchanged.

Column shape verified against the project's own established convention
(TimestampMixin's own definition, and the identical `deleted_at
TIMESTAMPTZ` pattern used for every table in 0001_initial_schema.py):
nullable, no server_default, no index — existing rows all become
deleted_at = NULL (i.e. "not deleted"), which is the correct,
non-destructive default for every row created before this migration.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lesson_progress", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("lesson_progress", "deleted_at")
