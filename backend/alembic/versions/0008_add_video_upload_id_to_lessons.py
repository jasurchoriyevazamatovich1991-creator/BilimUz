"""Add video_upload_id to lessons (Sprint 35)

Approved architecture: reuse the existing Sprint 27 R2 infrastructure —
no parallel media system. `lessons.video_upload_id` (nullable FK ->
uploads.id, ON DELETE SET NULL — matches migration 0007's
question_media.upload_id rationale exactly: deleting an Upload should
not cascade-delete the Lesson row, only lose its video reference) lets
a lesson's video be a REAL, R2-backed, signed-URL-accessible Upload row
instead of only the existing raw `video` text URL.

The existing `lessons.video` (Text) column is completely UNCHANGED —
every lesson written before Sprint 35 keeps working exactly as before
via that column. `video_upload_id` is purely additive; NULL means "no
R2 video, fall back to the legacy `video` URL field if present."

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lessons", sa.Column("video_upload_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_lessons_video_upload_id", "lessons", "uploads", ["video_upload_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_lessons_video_upload_id", "lessons", ["video_upload_id"])


def downgrade() -> None:
    op.drop_index("ix_lessons_video_upload_id", table_name="lessons")
    op.drop_constraint("fk_lessons_video_upload_id", "lessons", type_="foreignkey")
    op.drop_column("lessons", "video_upload_id")
