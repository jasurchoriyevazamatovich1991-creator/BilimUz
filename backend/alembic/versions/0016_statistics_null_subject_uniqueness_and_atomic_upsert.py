"""Sprint 69 — Statistics correctness + concurrency fix (F1 + F2)

Fully additive/corrective. No existing column is dropped, renamed, or
retyped. Fixes two real, audit-confirmed defects:

F1 — `statistics` (results module) had NO unique constraint at all on
(user_id, subject_id). ResultService._update_statistics() used an
unprotected check-then-act (get-then-create-or-update) pattern, so two
concurrent first-time writes for the same (user_id, subject_id) could
both insert, producing duplicate rows — and once duplicated,
StatisticsRepository.get_by_user_and_subject()'s scalar_one_or_none()
would raise MultipleResultsFound on every subsequent read for that key.

F2 — `monthly_statistics`/`daily_statistics` already had a plain
UNIQUE(user_id, subject_id, ...) constraint (migration 0001) and an
atomic INSERT ... ON CONFLICT DO UPDATE upsert (Sprint 64), but a plain
PostgreSQL UNIQUE constraint treats NULL <> NULL, so two rows with
subject_id IS NULL for the same (user_id, month, year) / (user_id,
stat_date) were never recognized as conflicting — ON CONFLICT silently
never fired for the NULL-subject_id case, reproduced directly against
this exact constraint/statement during the Sprint 69 audit.

Fix for both: PostgreSQL 16 (confirmed the project's version) supports
`UNIQUE ... NULLS NOT DISTINCT`, which treats all NULLs in the
constrained columns as equal to each other for conflict-detection
purposes — the single cleanest, PostgreSQL-native fix that lets the
existing (F2) or newly added (F1) `ON CONFLICT DO UPDATE` upsert keep
working unchanged for both the NULL-subject_id and non-NULL cases,
with no SELECT-before-INSERT and no application-level locking.

Design decisions:
- `statistics` gets a new, plain (non-partial) table-level UNIQUE
  NULLS NOT DISTINCT (user_id, subject_id) constraint, named
  uq_statistics_user_id_subject_id. A partial (WHERE deleted_at IS
  NULL) index was considered, since `statistics` does carry a
  deleted_at column (TimestampMixin) — but StatisticsRepository has no
  delete/soft_delete method at all (confirmed by inspection), so no
  code path ever sets statistics.deleted_at, and a plain constraint
  exactly mirrors this codebase's own existing convention for a table
  in the same situation (ResultSection's uq_result_sections_result_id_
  section_id is also a plain, non-partial UniqueConstraint despite
  ResultSection also having an unused deleted_at column). Introducing
  a partial-unique-index idiom that exists nowhere else in this
  project, for a delete path that doesn't exist, would be unrelated
  scope creep.
- `monthly_statistics`/`daily_statistics` keep their existing
  constraint NAMES (uq_monthly_statistics_user_subject_month_year,
  uq_daily_statistics_user_subject_date) so MonthlyStatisticsRepository
  .upsert()/DailyStatisticsRepository.upsert()'s existing
  `constraint="..."` arguments need no code change beyond the SQL
  behavior itself — only the constraint's NULL semantics change said
  constraints are dropped and recreated with NULLS NOT DISTINCT.

Data reconciliation (required before any of the three constraints can
be created, since a duplicate would violate it immediately): this
project's own test database currently has ZERO duplicate rows in any
of the three tables (verified directly during the Sprint 69 audit), so
the upgrade() step below is a no-op in this database today — but the
migration is written to be safe against a production database that
DOES already contain duplicates from before this fix (exactly the
scenario F1/F2 describe), per the sprint's explicit requirement. Each
reconciliation step:
  1. Groups existing (non-deleted, for `statistics`) rows by the
     table's real logical key — plain SQL GROUP BY already treats
     multiple NULL subject_id values as one group, unlike a UNIQUE
     constraint, so this naturally finds exactly the rows that would
     otherwise violate the new constraint.
  2. For any group with more than one row, merges them into a single
     surviving row using the existing application-level aggregate
     semantics (never invented ones):
       - tests_taken / correct_answers / wrong_answers: SUMmed across
         the duplicate rows — mirrors ResultService._update_statistics
         ()'s own tests_taken/correct_answers/wrong_answers += logic,
         and AnalyticsService._sum_daily_by_user_subject()'s existing
         "sum tests_taken across rows for the same key" semantics for
         monthly_statistics.
       - avg_score (statistics, monthly_statistics): a tests_taken-
         weighted average across the duplicate rows — the generalized
         form of ResultService._update_statistics()'s own running-
         average formula ((old_avg*old_count)+new)/(new_count), which
         is exactly the tests_taken-weighted mean of all contributing
         percentages; NULL avg_score rows are treated as contributing
         0 score across their own tests_taken (never letting a NULL
         silently vanish the row's own test count from the
         denominator).
       - created_at: the earliest of the duplicate rows' created_at
         (the statistic conceptually "started" being tracked then).
       - updated_at: now() (this migration is itself an update).
       - the surviving row's id is deterministically the duplicate
         group's MIN(id) — arbitrary but stable, and irrelevant to any
         code path (nothing depends on statistics/monthly_statistics/
         daily_statistics ids being any particular value).
     The other, now-redundant rows in the group are then hard-deleted.
     Nothing is "silently deleted" without its aggregate value having
     first been folded into the surviving row — nothing is lost.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- F1: statistics ---------------------------------------------------

_RECONCILE_STATISTICS = """
WITH grp AS (
    SELECT user_id, subject_id
    FROM statistics
    WHERE deleted_at IS NULL
    GROUP BY user_id, subject_id
    HAVING count(*) > 1
),
agg AS (
    SELECT
        s.user_id,
        s.subject_id,
        (array_agg(s.id ORDER BY s.created_at, s.id::text))[1] AS keep_id,
        SUM(s.tests_taken) AS tests_taken,
        SUM(s.correct_answers) AS correct_answers,
        SUM(s.wrong_answers) AS wrong_answers,
        CASE WHEN SUM(s.tests_taken) > 0
             THEN SUM(COALESCE(s.avg_score, 0) * s.tests_taken) / SUM(s.tests_taken)
             ELSE NULL
        END AS avg_score,
        MIN(s.created_at) AS created_at
    FROM statistics s
    JOIN grp g ON g.user_id = s.user_id AND s.subject_id IS NOT DISTINCT FROM g.subject_id
    WHERE s.deleted_at IS NULL
    GROUP BY s.user_id, s.subject_id
)
UPDATE statistics s
SET tests_taken = agg.tests_taken,
    correct_answers = agg.correct_answers,
    wrong_answers = agg.wrong_answers,
    avg_score = agg.avg_score,
    created_at = agg.created_at,
    updated_at = now()
FROM agg
WHERE s.id = agg.keep_id;
"""

_DELETE_DUPLICATE_STATISTICS = """
WITH grp AS (
    SELECT user_id, subject_id, (array_agg(id ORDER BY created_at, id::text))[1] AS keep_id
    FROM statistics
    WHERE deleted_at IS NULL
    GROUP BY user_id, subject_id
    HAVING count(*) > 1
)
DELETE FROM statistics s
USING grp g
WHERE s.deleted_at IS NULL
  AND s.user_id = g.user_id
  AND s.subject_id IS NOT DISTINCT FROM g.subject_id
  AND s.id <> g.keep_id;
"""

# --- F2: monthly_statistics --------------------------------------------

_RECONCILE_MONTHLY = """
WITH grp AS (
    SELECT user_id, subject_id, month, year
    FROM monthly_statistics
    GROUP BY user_id, subject_id, month, year
    HAVING count(*) > 1
),
agg AS (
    SELECT
        m.user_id, m.subject_id, m.month, m.year,
        (array_agg(m.id ORDER BY m.created_at, m.id::text))[1] AS keep_id,
        SUM(m.tests_taken) AS tests_taken,
        CASE WHEN SUM(m.tests_taken) > 0
             THEN SUM(COALESCE(m.avg_score, 0) * m.tests_taken) / SUM(m.tests_taken)
             ELSE NULL
        END AS avg_score,
        MIN(m.created_at) AS created_at
    FROM monthly_statistics m
    JOIN grp g ON g.user_id = m.user_id AND m.subject_id IS NOT DISTINCT FROM g.subject_id
              AND g.month = m.month AND g.year = m.year
    GROUP BY m.user_id, m.subject_id, m.month, m.year
)
UPDATE monthly_statistics m
SET tests_taken = agg.tests_taken,
    avg_score = agg.avg_score,
    created_at = agg.created_at,
    updated_at = now()
FROM agg
WHERE m.id = agg.keep_id;
"""

_DELETE_DUPLICATE_MONTHLY = """
WITH grp AS (
    SELECT user_id, subject_id, month, year, (array_agg(id ORDER BY created_at, id::text))[1] AS keep_id
    FROM monthly_statistics
    GROUP BY user_id, subject_id, month, year
    HAVING count(*) > 1
)
DELETE FROM monthly_statistics m
USING grp g
WHERE m.user_id = g.user_id
  AND m.subject_id IS NOT DISTINCT FROM g.subject_id
  AND m.month = g.month AND m.year = g.year
  AND m.id <> g.keep_id;
"""

# --- F2: daily_statistics ------------------------------------------------

_RECONCILE_DAILY = """
WITH grp AS (
    SELECT user_id, subject_id, stat_date
    FROM daily_statistics
    GROUP BY user_id, subject_id, stat_date
    HAVING count(*) > 1
),
agg AS (
    SELECT
        d.user_id, d.subject_id, d.stat_date,
        (array_agg(d.id ORDER BY d.created_at, d.id::text))[1] AS keep_id,
        SUM(d.tests_taken) AS tests_taken,
        SUM(d.correct_answers) AS correct_answers,
        SUM(d.wrong_answers) AS wrong_answers,
        MIN(d.created_at) AS created_at
    FROM daily_statistics d
    JOIN grp g ON g.user_id = d.user_id AND d.subject_id IS NOT DISTINCT FROM g.subject_id
              AND g.stat_date = d.stat_date
    GROUP BY d.user_id, d.subject_id, d.stat_date
)
UPDATE daily_statistics d
SET tests_taken = agg.tests_taken,
    correct_answers = agg.correct_answers,
    wrong_answers = agg.wrong_answers,
    created_at = agg.created_at,
    updated_at = now()
FROM agg
WHERE d.id = agg.keep_id;
"""

_DELETE_DUPLICATE_DAILY = """
WITH grp AS (
    SELECT user_id, subject_id, stat_date, (array_agg(id ORDER BY created_at, id::text))[1] AS keep_id
    FROM daily_statistics
    GROUP BY user_id, subject_id, stat_date
    HAVING count(*) > 1
)
DELETE FROM daily_statistics d
USING grp g
WHERE d.user_id = g.user_id
  AND d.subject_id IS NOT DISTINCT FROM g.subject_id
  AND d.stat_date = g.stat_date
  AND d.id <> g.keep_id;
"""


def upgrade() -> None:
    # --- F1: statistics — reconcile any pre-existing duplicates, then
    # add the missing unique constraint (NULLS NOT DISTINCT so a NULL
    # subject_id participates in uniqueness exactly like a real UUID).
    op.execute(sa.text(_RECONCILE_STATISTICS))
    op.execute(sa.text(_DELETE_DUPLICATE_STATISTICS))
    op.create_unique_constraint(
        "uq_statistics_user_id_subject_id",
        "statistics",
        ["user_id", "subject_id"],
        postgresql_nulls_not_distinct=True,
    )

    # --- F2: monthly_statistics / daily_statistics — reconcile any
    # pre-existing NULL-subject_id duplicates (the exact defect
    # reproduced during the Sprint 69 audit), then replace the plain
    # UNIQUE constraints with NULLS NOT DISTINCT equivalents, same
    # names, so MonthlyStatisticsRepository.upsert()/
    # DailyStatisticsRepository.upsert()'s constraint="..." arguments
    # keep working unchanged.
    op.execute(sa.text(_RECONCILE_MONTHLY))
    op.execute(sa.text(_DELETE_DUPLICATE_MONTHLY))
    op.drop_constraint("uq_monthly_statistics_user_subject_month_year", "monthly_statistics", type_="unique")
    op.create_unique_constraint(
        "uq_monthly_statistics_user_subject_month_year",
        "monthly_statistics",
        ["user_id", "subject_id", "month", "year"],
        postgresql_nulls_not_distinct=True,
    )

    op.execute(sa.text(_RECONCILE_DAILY))
    op.execute(sa.text(_DELETE_DUPLICATE_DAILY))
    op.drop_constraint("uq_daily_statistics_user_subject_date", "daily_statistics", type_="unique")
    op.create_unique_constraint(
        "uq_daily_statistics_user_subject_date",
        "daily_statistics",
        ["user_id", "subject_id", "stat_date"],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    # Reverses the constraint changes only. Reconciled/merged duplicate
    # rows from upgrade() are NOT un-merged (that information — which
    # original rows existed before the merge — is not recoverable, the
    # same way any other data-fixing migration's downgrade cannot
    # un-fix data); this mirrors standard Alembic practice for
    # corrective data migrations elsewhere in this project's history.
    op.drop_constraint("uq_daily_statistics_user_subject_date", "daily_statistics", type_="unique")
    op.create_unique_constraint(
        "uq_daily_statistics_user_subject_date",
        "daily_statistics",
        ["user_id", "subject_id", "stat_date"],
    )

    op.drop_constraint("uq_monthly_statistics_user_subject_month_year", "monthly_statistics", type_="unique")
    op.create_unique_constraint(
        "uq_monthly_statistics_user_subject_month_year",
        "monthly_statistics",
        ["user_id", "subject_id", "month", "year"],
    )

    op.drop_constraint("uq_statistics_user_id_subject_id", "statistics", type_="unique")
