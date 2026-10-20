"""Task 3 — media attached to a QuestionGroup (e.g. IELTS Listening
section audio shared by all of the group's questions).

Fully additive: one new table, no existing table, column, constraint or
row is touched. Why a new table rather than reusing `question_media`:
`question_media.question_id` is NOT NULL and every existing query
assumes each row belongs to one question; making it nullable would
change the meaning of existing data and code paths.

- group_id   -> question_groups.id, ON DELETE CASCADE
- upload_id  -> uploads.id, NOT NULL (always a real, private Upload;
                no file_url copy is stored)
- media_type -> 'audio' | 'image' (CHECK), derived server-side from the
                Upload's file_type
- created_at/updated_at/deleted_at, created_by/updated_by
- partial UNIQUE (group_id, upload_id) WHERE deleted_at IS NULL

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "question_group_media",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("question_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("upload_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("media_type IN ('audio', 'image')", name="ck_question_group_media_type_allowed"),
    )
    op.create_index("ix_question_group_media_group_id", "question_group_media", ["group_id"])
    op.create_index(
        "uq_question_group_media_active_group_upload", "question_group_media", ["group_id", "upload_id"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_question_group_media_active_group_upload", table_name="question_group_media")
    op.drop_index("ix_question_group_media_group_id", table_name="question_group_media")
    op.drop_table("question_group_media")
