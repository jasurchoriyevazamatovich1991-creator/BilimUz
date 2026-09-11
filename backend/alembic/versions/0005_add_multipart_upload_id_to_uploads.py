"""Add multipart_upload_id to uploads (Sprint 27 Amendment — 2GB video + R2 Multipart Upload)

Approved architecture: reuse the existing `Upload` row for multipart
state, no new Media/File model. Only ONE new column is genuinely
required — `multipart_upload_id`, R2's own session identifier for an
in-progress multipart upload, needed so later part-url/complete/abort
calls can be tied back to the right R2-side session. Everything else
needed to track multipart progress (total_parts, part_size) is either
derivable from `size_bytes` (already a column) via the centralized
constants, or is per-request state (part_number, ETag) that belongs in
the request/response schema, not persisted rows — per the explicit
instruction not to store presigned URLs or redundant fields.

Nullable: every non-multipart upload (the original synchronous flow,
and the existing single-PUT presigned flow from the Sprint 27 baseline)
never sets this column at all.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "uploads",
        sa.Column("multipart_upload_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("uploads", "multipart_upload_id")
