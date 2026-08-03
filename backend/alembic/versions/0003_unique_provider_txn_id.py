"""Add UNIQUE constraint on transactions.provider_txn_id

Sprint 9 (AI, Payments) approved decision: implement BOTH service-layer
idempotency (check-then-insert, in payments/repository.py) AND this
database-level UNIQUE constraint — the stronger guarantee, closing a
theoretical race condition where two webhook deliveries for the same
provider transaction are processed concurrently and both pass a
check-then-insert idempotency check before either commits.

provider_txn_id is nullable (a transaction row can exist before the
provider's ID is known, e.g. immediately after payment initiation) — a
partial UNIQUE index (WHERE provider_txn_id IS NOT NULL) is used instead
of a plain UNIQUE constraint, since Postgres already treats multiple
NULLs as non-conflicting under a normal UNIQUE constraint, but a partial
index makes that intent explicit and avoids ambiguity for anyone reading
the schema later.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-02

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_transactions_provider_txn_id",
        "transactions",
        ["provider_txn_id"],
        unique=True,
        postgresql_where="provider_txn_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_transactions_provider_txn_id", table_name="transactions")
