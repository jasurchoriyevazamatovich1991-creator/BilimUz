"""Add nullable lesson_id FK to uploads (Sprint 27 — R2 Media Storage)

Approved architecture: `uploads` is reused as the universal media table
(no new parallel Upload/Media model created — see
docs/Sprint27_R2_Media_Storage.md's audit section). The only structural
gap for linking media to educational content was a foreign key to
`lessons` — Subject/Grade/Topic are all derivable via
lesson -> topic -> subject_id/grade_id, so no redundant FK columns for
those are added (would violate normalization for no real benefit).

Nullable: an upload is not required to be lesson-linked (the existing
Sprint 8 "personal file" use case — e.g. a raw multipart upload with no
lesson context — must keep working unchanged).

ON DELETE SET NULL (not CASCADE): deleting a Lesson should not silently
delete potentially-large R2-backed media rows/objects as a side effect
of an unrelated Lesson-delete action — matches this platform's general
preference for explicit, visible cleanup over cascading deletes for
anything storage-costly (see uploads/README.md's own soft-delete
exception rationale for a similar "storage isn't free" consideration).

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "uploads",
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_uploads_lesson_id",
        "uploads",
        "lessons",
        ["lesson_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_uploads_lesson_id", "uploads", ["lesson_id"])


def downgrade() -> None:
    op.drop_index("ix_uploads_lesson_id", table_name="uploads")
    op.drop_constraint("fk_uploads_lesson_id", "uploads", type_="foreignkey")
    op.drop_column("uploads", "lesson_id")
