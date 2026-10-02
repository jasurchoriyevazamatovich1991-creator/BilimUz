"""Sprint 72 — CONC-1: Certificate issuance concurrency fix.

Fully additive/corrective. No existing column is dropped, renamed, or
retyped. Fixes one real, Sprint-71-audit-confirmed defect:

CONC-1 — CertificateService.issue() used an unprotected check-then-act
pattern: CertificateRepository.get_by_user_and_test(user_id, test_id)
(a SELECT, joined through `results` since `certificates` had no direct
test_id column) followed by an unconditional create() if nothing was
found. Two concurrent issue() calls for the same (user_id, test_id) —
e.g. a double-click or a retried request — could both take the
"not found" branch and both create a Certificate (+ its own
CertificateVerification row and PDF), producing two certificates for
the same passed test instead of the approved idempotent "return the
existing one" behavior.

Design decision (see CertificateRepository.get_by_user_and_test()'s
own pre-existing docstring, which already names (user_id, test_id) as
"the approved idempotency key"): a genuine DB-level UNIQUE constraint
on that exact key is impossible without this migration, because
PostgreSQL cannot express a unique INDEX or CONSTRAINT whose key spans
a joined table (test_id lives on `results`, reached only via
`certificates.result_id`) — a unique index's expression must be an
immutable function of the row's own columns. Per this sprint's own
explicit preference order ("1. DB-level uniqueness for the actual
certificate identity. 2. PostgreSQL atomic handling or row lock.
3. Preserve idempotent behavior"), this migration denormalizes a new
`test_id` column directly onto `certificates` (backfilled from the
already-existing `results.test_id` via the certificate's `result_id`,
never invented), then adds a genuine UNIQUE(user_id, test_id)
constraint on it. This intentionally introduces one documented column
of drift from schema_v2.sql's original `certificates` table shape,
exactly as migration 0016 introduced (for `statistics`) a constraint
schema_v2.sql never specified — both are additive, audit-driven
correctness fixes, not an unrelated redesign.

`test_id` is NOT nullable: every Certificate's `result_id` already
points to an existing Result (ForeignKey, non-nullable since Sprint 7),
and every Result has a non-nullable `test_id` (results/models.py) — so
the backfill in upgrade() below can never leave a NULL behind, and a
plain (non-NULLS-NOT-DISTINCT) UNIQUE constraint is correct: unlike
Statistics/Ranking's nullable subject_id, there is no "NULL should
still conflict" case to handle here at all.

Data reconciliation (required before the constraint can be created,
since a duplicate would violate it immediately): this project's own
test database currently has ZERO rows in `certificates` at all
(confirmed directly during Sprint 72's design phase), so the
reconciliation step below is a no-op here today — but, per this
sprint's explicit requirement, it is written to be safe against a
production database that already has duplicate certificates issued
under the old check-then-act race. Since a Certificate (unlike
Statistics' running counters) has no aggregate value to merge — two
certificates for the same (user_id, test_id) are the same logical
grant, not two partial contributions — reconciliation keeps the
earliest-issued certificate per (user_id, test_id) group (the one a
correct idempotent issue() would itself have returned on every
subsequent call) and hard-deletes the rest; each deleted certificate's
own CertificateVerification row(s) cascade-delete automatically
(certificate_verification.certificate_id has ON DELETE CASCADE,
models.py) — nothing is left orphaned.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BACKFILL_TEST_ID = """
UPDATE certificates c
SET test_id = r.test_id
FROM results r
WHERE r.id = c.result_id;
"""

_DELETE_DUPLICATE_CERTIFICATES = """
WITH grp AS (
    SELECT user_id, test_id, (array_agg(id ORDER BY created_at, id::text))[1] AS keep_id
    FROM certificates
    WHERE deleted_at IS NULL
    GROUP BY user_id, test_id
    HAVING count(*) > 1
)
DELETE FROM certificates c
USING grp g
WHERE c.deleted_at IS NULL
  AND c.user_id = g.user_id
  AND c.test_id = g.test_id
  AND c.id <> g.keep_id;
"""


def upgrade() -> None:
    # 1. Add the new column nullable first (a NOT NULL column can't be
    #    added to a populated table without a default) — backfilled
    #    immediately below, then tightened to NOT NULL.
    op.add_column("certificates", sa.Column("test_id", UUID(as_uuid=True), nullable=True))
    op.execute(sa.text(_BACKFILL_TEST_ID))
    op.alter_column("certificates", "test_id", nullable=False)
    op.create_foreign_key(
        "fk_certificates_test_id_tests", "certificates", "tests", ["test_id"], ["id"],
    )

    # 2. Reconcile any pre-existing duplicate certificates for the same
    #    (user_id, test_id) BEFORE the constraint can be created.
    op.execute(sa.text(_DELETE_DUPLICATE_CERTIFICATES))

    # 3. The actual DB-level uniqueness fix — CONC-1's primary defense.
    op.create_unique_constraint(
        "uq_certificates_user_id_test_id", "certificates", ["user_id", "test_id"],
    )


def downgrade() -> None:
    # Reverses the column + constraint additions only. Certificates
    # hard-deleted by upgrade()'s reconciliation step are NOT
    # recoverable — same standard practice this project already
    # follows for corrective data migrations (migrations 0016/0017).
    op.drop_constraint("uq_certificates_user_id_test_id", "certificates", type_="unique")
    op.drop_constraint("fk_certificates_test_id_tests", "certificates", type_="foreignkey")
    op.drop_column("certificates", "test_id")
