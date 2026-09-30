"""
Data-access layer for Result, Statistics, Ranking — three repositories
in one file, same cohesive-module reasoning as questions/repository.py
and permissions/repository.py.
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.results.models import Ranking, Result, ResultSection, Statistics


class ResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, result_id: uuid.UUID) -> Result | None:
        stmt = select(Result).where(Result.id == result_id, Result.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_attempt_id(self, attempt_id: uuid.UUID) -> Result | None:
        stmt = select(Result).where(Result.attempt_id == attempt_id, Result.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_user_and_test(self, user_id: uuid.UUID, test_id: uuid.UUID) -> Result | None:
        """Used by the `certificates` module (read-only) for its
        (user_id, test_id) idempotency check — see that module's README."""
        stmt = select(Result).where(
            Result.user_id == user_id, Result.test_id == test_id, Result.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID, page: int, per_page: int, test_id: uuid.UUID | None, sort: str) -> tuple[list[Result], int]:
        stmt = select(Result).where(Result.user_id == user_id, Result.deleted_at.is_(None))
        if test_id:
            stmt = stmt.where(Result.test_id == test_id)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        descending = sort.startswith("-")
        field_name = sort.lstrip("-")
        column = getattr(Result, field_name, Result.created_at)
        stmt = stmt.order_by(column.desc() if descending else column.asc())
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def list_for_subject(self, subject_id: uuid.UUID | None) -> list[Result]:
        """Used by RankingService.recompute() — every result scoped to a
        subject (via its test), unpaginated (recompute needs the full set)."""
        from app.modules.tests.models import Test
        stmt = select(Result).where(Result.deleted_at.is_(None))
        if subject_id:
            stmt = stmt.join(Test, Test.id == Result.test_id).where(Test.subject_id == subject_id)
        return list(self.db.execute(stmt).scalars().all())

    def list_in_date_range(self, start: date, end: date) -> list[Result]:
        """Read-only entry point for the future `analytics` module (per
        the approved architecture — analytics reads results, results
        never writes to analytics)."""
        stmt = select(Result).where(
            Result.deleted_at.is_(None),
            func.date(Result.created_at) >= start,
            func.date(Result.created_at) <= end,
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, result: Result) -> Result:
        self.db.add(result)
        self.db.flush()
        return result

    def commit(self) -> None:
        self.db.commit()


class ResultSectionRepository:
    """Sprint 54 — ResultSection creation during Result creation
    (generic section-level raw scoring foundation). Mirrors
    ResultRepository's own shape exactly, same cohesive-module
    reasoning as the other repositories in this file.

    No update()/delete() — ResultSection rows are write-once per
    (result, section) by design (a Result is itself immutable once
    created; re-running create_result() for an already-existing
    attempt returns the existing Result and never touches its
    sections again, see ResultService.create_result())."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_result_and_section(self, result_id: uuid.UUID, section_id: uuid.UUID) -> ResultSection | None:
        stmt = select(ResultSection).where(
            ResultSection.result_id == result_id, ResultSection.section_id == section_id, ResultSection.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_result(self, result_id: uuid.UUID) -> list[ResultSection]:
        stmt = select(ResultSection).where(ResultSection.result_id == result_id, ResultSection.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def create(self, result_section: ResultSection) -> ResultSection:
        # Safe/idempotent under concurrency by construction, not by a
        # try/except here: the caller (ResultService.create_result())
        # only ever reaches this method while holding the locked
        # TestAttempt row (AttemptRepository.get_by_id_locked) acquired
        # BEFORE the Result-existence check — see that method's own
        # docstring. A second concurrent request for the same attempt
        # blocks on that lock and, once unblocked, finds the Result
        # (and therefore its ResultSection rows) already committed, so
        # it returns the existing Result instead of ever calling this
        # method again for the same (result_id, section_id) pair. The
        # UNIQUE(result_id, section_id) DB constraint remains as the
        # final backstop, exactly as Result.attempt_id's UNIQUE
        # constraint backstops Result creation.
        self.db.add(result_section)
        self.db.flush()
        return result_section


class StatisticsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_and_subject(self, user_id: uuid.UUID, subject_id: uuid.UUID | None) -> Statistics | None:
        stmt = select(Statistics).where(
            Statistics.user_id == user_id, Statistics.subject_id == subject_id, Statistics.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, stats: Statistics) -> Statistics:
        self.db.add(stats)
        self.db.flush()
        return stats

    def update(self, stats: Statistics, data: dict) -> Statistics:
        for field, value in data.items():
            setattr(stats, field, value)
        self.db.flush()
        return stats

    def upsert_after_result(self, user_id: uuid.UUID, subject_id: uuid.UUID | None, correct: int, wrong: int, percentage: float) -> Statistics:
        """Sprint 69 — F1. Replaces the former get()-then-create()-or-
        update() check-then-act path (still available above as create()/
        update(), kept for any other caller and for direct construction
        in tests, but no longer used by ResultService._update_statistics()).

        That check-then-act path had no database-level protection at
        all — uq_statistics_user_id_subject_id (migration 0016) did not
        exist before this sprint — so two concurrent first-time writes
        for the same (user_id, subject_id) could both take the "not
        found" branch and both INSERT, producing duplicate rows; once
        duplicated, every subsequent get_by_user_and_subject() call for
        that key would raise MultipleResultsFound (scalar_one_or_none()
        against >1 row).

        This method makes the same logical operation ("increment this
        user/subject's running stats by one more test's worth of
        correct/wrong answers and percentage, or create the row if this
        is the first test") a single atomic
        INSERT ... ON CONFLICT DO UPDATE, same established pattern as
        AnswerRepository.upsert() (Sprint 58) and this project's
        analytics-module MonthlyStatisticsRepository/
        DailyStatisticsRepository.upsert() (Sprint 64). Correctness
        under concurrency:

        - Two concurrent first-time writes for the same key: Postgres
          serializes the two INSERTs against the same unique index
          entry — one wins the plain INSERT, the other's ON CONFLICT
          clause fires and its DO UPDATE runs (waiting on the winning
          row's lock, exactly like any other row-level UPDATE), so the
          result is exactly one row with tests_taken=2 (never two rows
          with tests_taken=1 each, and never a crash).
        - Two concurrent updates to an existing row: same lock-then-
          update semantics — the DO UPDATE's SET expressions read
          statistics.tests_taken/avg_score from the row AS OF the time
          each statement acquires the row lock (not a stale
          Python-side read taken before the write, which is exactly
          what made the old code's `((float(stats.avg_score or 0) *
          stats.tests_taken) + percentage) / new_count` computation in
          Python racy) — so the second writer's update is computed
          against the first writer's already-committed result, and no
          update is lost.
        - avg_score semantics are UNCHANGED from ResultService.
          _update_statistics()'s original formula — this is the same
          running (tests_taken-weighted) average, expressed as a SQL
          expression over the CURRENT row (statistics.avg_score,
          statistics.tests_taken) and the EXCLUDED (this call's own
          percentage) instead of a Python-side read-modify-write:
              new_count = statistics.tests_taken + 1
              new_avg   = ((statistics.avg_score * statistics.tests_taken)
                           + EXCLUDED.avg_score) / new_count
          EXCLUDED.avg_score carries this call's own `percentage`
          (via the INSERT VALUES below, which sets avg_score=percentage
          for the not-yet-existing-row case) — exactly mirroring how
          the original Python code used the same `percentage` value in
          both branches (as avg_score for a fresh row, or as the
          `+ percentage` term for the running-average formula).
        """
        stmt = (
            pg_insert(Statistics)
            .values(
                user_id=user_id, subject_id=subject_id, tests_taken=1,
                correct_answers=correct, wrong_answers=wrong, avg_score=percentage,
            )
        )
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            constraint="uq_statistics_user_id_subject_id",
            set_={
                "tests_taken": Statistics.tests_taken + 1,
                "correct_answers": Statistics.correct_answers + excluded.correct_answers,
                "wrong_answers": Statistics.wrong_answers + excluded.wrong_answers,
                "avg_score": func.round(
                    (func.coalesce(Statistics.avg_score, 0) * Statistics.tests_taken + excluded.avg_score)
                    / (Statistics.tests_taken + 1),
                    2,
                ),
                "updated_at": func.now(),
            },
        )
        self.db.execute(stmt)
        self.db.flush()
        return self.get_by_user_and_subject(user_id, subject_id)


class RankingRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_subject_and_period(self, subject_id: uuid.UUID | None, period: str) -> list[Ranking]:
        stmt = select(Ranking).where(
            Ranking.subject_id == subject_id, Ranking.period == period, Ranking.deleted_at.is_(None)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get(self, user_id: uuid.UUID, subject_id: uuid.UUID | None, period: str) -> Ranking | None:
        stmt = select(Ranking).where(
            Ranking.user_id == user_id, Ranking.subject_id == subject_id,
            Ranking.period == period, Ranking.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def upsert(self, user_id: uuid.UUID, subject_id: uuid.UUID | None, period: str, score: float, rank: int) -> Ranking:
        existing = self.get(user_id, subject_id, period)
        if existing:
            existing.score = score
            existing.rank = rank
            existing.updated_at = datetime.now(timezone.utc)
            self.db.flush()
            return existing
        row = Ranking(user_id=user_id, subject_id=subject_id, period=period, score=score, rank=rank)
        self.db.add(row)
        self.db.flush()
        return row

    def commit(self) -> None:
        self.db.commit()
