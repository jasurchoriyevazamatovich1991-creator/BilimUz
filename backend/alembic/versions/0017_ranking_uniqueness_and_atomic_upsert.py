"""Sprint 72 — RANK-2: Ranking concurrency fix.

Fully additive/corrective. No existing column is dropped, renamed, or
retyped. Fixes one real, Sprint-71-audit-confirmed defect:

RANK-2 — `ranking` (results module) had NO unique constraint at all on
(user_id, subject_id, period). RankingRepository.upsert() used an
unprotected check-then-act (get()-then-create-or-update) pattern — the
exact same shape as the F1 defect migration 0016 already fixed for
`statistics` — so two concurrent writes for the same (user_id,
subject_id, period) key (e.g. two overlapping RankingService.recompute()
runs, or a recompute racing a future per-user ranking write) could both
take the "not found" branch and both INSERT, producing duplicate rows
for the same logical ranking slot.

Fix: same PostgreSQL-native approach as migration 0016 — `UNIQUE ...
NULLS NOT DISTINCT (user_id, subject_id, period)`, so `subject_id IS
NULL` (the "overall, not subject-scoped" ranking bucket — `Ranking.
subject_id` is nullable, confirmed in results/models.py, same situation
as Statistics.subject_id) participates in uniqueness exactly like a
real subject UUID. This lets RankingRepository.upsert() become a single
atomic `INSERT ... ON CONFLICT DO UPDATE`, same established pattern as
StatisticsRepository.upsert_after_result() (Sprint 69) and AnswerRepository
.upsert() (Sprint 58) — no SELECT-before-INSERT, no application-level
locking.

Design decisions:
- Plain (non-partial) table-level UNIQUE NULLS NOT DISTINCT
  (user_id, subject_id, period), named uq_ranking_user_subject_period —
  mirrors migration 0016's own reasoning for `statistics`: `ranking`
  does carry an unused `deleted_at` column (TimestampMixin), but
  RankingRepository has no delete/soft_delete method at all (confirmed
  by inspection), so no code path ever sets ranking.deleted_at, and a
  partial-unique-index idiom for a delete path that doesn't exist would
  be unrelated scope creep (same conclusion 0016 reached for the
  equivalent situation on `statistics`).
- Unlike Statistics (whose upsert() SUMS running counters — tests_taken,
  correct_answers, etc. — so a genuine aggregate-merge is required when
  reconciling pre-existing duplicates), Ranking's score/rank are not
  accumulated: RankingService.recompute() always fully recomputes and
  overwrites them from the current result set. There is therefore no
  meaningful "merge" of two duplicate ranking rows' score/rank — one is
  simply the stale leftover of the other. Reconciliation here keeps the
  most-recently-updated row per (user_id, subject_id, period) group
  (ties broken by id) and hard-deletes the rest, mirroring how a correct
  recompute() would itself have left exactly one current row behind.

Data reconciliation (required before the constraint can be created,
since a duplicate would violate it immediately): this project's own
test database currently has ZERO rows in `ranking` at all (confirmed
directly during Sprint 72's design phase — RankingService.recompute()
has simply never been exercised against this database), so the
upgrade() step below is a no-op here today — but the migration is
written to be safe against a production database that already has
duplicates, per this sprint's explicit requirement.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DELETE_DUPLICATE_RANKING = """
WITH grp AS (
    SELECT user_id, subject_id, period,
           (array_agg(id ORDER BY updated_at DESC, id::text))[1] AS keep_id
    FROM ranking
    WHERE deleted_at IS NULL
    GROUP BY user_id, subject_id, period
    HAVING count(*) > 1
)
DELETE FROM ranking r
USING grp g
WHERE r.deleted_at IS NULL
  AND r.user_id = g.user_id
  AND r.subject_id IS NOT DISTINCT FROM g.subject_id
  AND r.period = g.period
  AND r.id <> g.keep_id;
"""


def upgrade() -> None:
    op.execute(sa.text(_DELETE_DUPLICATE_RANKING))
    op.create_unique_constraint(
        "uq_ranking_user_subject_period",
        "ranking",
        ["user_id", "subject_id", "period"],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    # Reverses the constraint only. Rows hard-deleted by upgrade()'s
    # reconciliation step are NOT recoverable — same standard Alembic
    # practice this project already follows for corrective data
    # migrations (see migration 0016's downgrade() for the identical
    # reasoning).
    op.drop_constraint("uq_ranking_user_subject_period", "ranking", type_="unique")
