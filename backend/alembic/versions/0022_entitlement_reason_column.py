"""Admin Management of Mock Test Entitlements — adds `reason` to
`entitlements`.

Fully additive. One new nullable column, no default needed (NULL is the
correct value for every existing row and for purchase-sourced
entitlements — there is no admin "reason" behind a purchase). No
existing column, constraint, or row value is touched.

Why this column: the task spec (§3) explicitly asks to "record the
granting administrator, source, timestamps, and reason where supported
by the existing schema." granted_by/source/timestamps already existed;
reason did not. Adding it here (rather than treating it as "not
supported, so skip it") lets an admin attach a short free-text
justification to a grant/extend/revoke action — useful for the audit
trail spec §5 asks the admin UI to show ("relevant action history").

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "entitlements",
        sa.Column("reason", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("entitlements", "reason")
