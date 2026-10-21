"""Task 6 — exam UI enhancements: mark for review, calculator, Speaking audio.

Fully additive (NULL/false for every existing row, i.e. no behavior change):
- test_attempts.review_marked_question_ids UUID[]  (navigation state only)
- exam_sections.calculator_enabled BOOLEAN NOT NULL DEFAULT false
- answers.audio_upload_id UUID -> uploads.id ON DELETE SET NULL
  (a private Upload; recordings are never exposed by public URL)

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_attempts", sa.Column("review_marked_question_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True))
    op.add_column("exam_sections", sa.Column("calculator_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("answers", sa.Column(
        "audio_upload_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("answers", "audio_upload_id")
    op.drop_column("exam_sections", "calculator_enabled")
    op.drop_column("test_attempts", "review_marked_question_ids")
