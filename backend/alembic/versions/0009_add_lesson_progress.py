"""Add lesson_progress table (Sprint 36 — Student Progress)

Approved architecture: additive, new table. Does not touch Lesson,
Upload, Test, Attempt, Result, or Certificate in any way — Sprint 35's
R2 video architecture (lessons.video_upload_id) is completely
unaffected.

`user_id`/`lesson_id` both use `ondelete="CASCADE"` — unlike
uploads.lesson_id (SET NULL, Sprint 27) or lessons.video_upload_id (SET
NULL, Sprint 35), a progress record has NO meaning once its user or
lesson no longer exists (there is nothing left to "track progress on"),
so cascading delete is the correct choice here — verified against the
existing `notifications.user_id` FK (also CASCADE) as the established
precedent for "this row is meaningless without its owning user."

UNIQUE(user_id, lesson_id) prevents duplicate progress rows for the
same student+lesson — this is also the natural index for the two real
query patterns this feature needs: "does THIS user have progress on
THIS lesson" (point lookup) and "all of THIS user's progress" (prefix
scan on user_id). No additional index is added beyond what the unique
constraint already provides.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lesson_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress_user_lesson"),
    )
    op.create_index("ix_lesson_progress_user_id", "lesson_progress", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_lesson_progress_user_id", table_name="lesson_progress")
    op.drop_table("lesson_progress")
