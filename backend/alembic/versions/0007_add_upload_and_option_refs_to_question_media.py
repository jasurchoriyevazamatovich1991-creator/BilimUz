"""Add upload_id and option_id to question_media (Sprint 32)

Approved architecture: reuse the existing Sprint 27 R2 `uploads`
infrastructure — no parallel media system. `question_media.upload_id`
(nullable FK -> uploads.id, ON DELETE SET NULL, matching the exact same
rationale as uploads.lesson_id in migration 0004 — deleting an upload
should not cascade-delete the question row's other content) lets a
question's media be tied to a REAL, R2-backed, signed-URL-accessible
Upload row instead of only a client-supplied raw file_url string (the
existing POST /questions/{id}/media endpoint accepted an arbitrary
http(s) URL with no ownership/authorization check at all — see Sprint
32's audit). The legacy `file_url` column is untouched and kept for
backward compatibility with any existing rows.

`question_media.option_id` (nullable FK -> question_options.id, ON
DELETE CASCADE — media attached to a specific option is meaningless
once that option is deleted, unlike the lesson case) — Phase 7's
"options can carry media too" requirement. NULL means the media
belongs to the question as a whole (existing behavior, unchanged);
set means it belongs to that specific option.

Both nullable, both purely additive — no existing data is touched, no
existing column is renamed or dropped, question_media.question_id
remains required exactly as before.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("question_media", sa.Column("upload_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_question_media_upload_id", "question_media", "uploads", ["upload_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column("question_media", sa.Column("option_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_question_media_option_id", "question_media", "question_options", ["option_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_question_media_option_id", "question_media", ["option_id"])


def downgrade() -> None:
    op.drop_index("ix_question_media_option_id", table_name="question_media")
    op.drop_constraint("fk_question_media_option_id", "question_media", type_="foreignkey")
    op.drop_column("question_media", "option_id")
    op.drop_constraint("fk_question_media_upload_id", "question_media", type_="foreignkey")
    op.drop_column("question_media", "upload_id")
