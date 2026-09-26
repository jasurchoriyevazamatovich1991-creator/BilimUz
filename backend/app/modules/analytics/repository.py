"""Data-access layer for DailyStatistics, MonthlyStatistics — two
repositories in one file."""
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.analytics.models import DailyStatistics, MonthlyStatistics


class DailyStatisticsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: uuid.UUID, subject_id: uuid.UUID | None, stat_date: date) -> DailyStatistics | None:
        stmt = select(DailyStatistics).where(
            DailyStatistics.user_id == user_id, DailyStatistics.subject_id == subject_id,
            DailyStatistics.stat_date == stat_date,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID, start: date, end: date, subject_id: uuid.UUID | None) -> list[DailyStatistics]:
        stmt = select(DailyStatistics).where(
            DailyStatistics.user_id == user_id,
            DailyStatistics.stat_date >= start, DailyStatistics.stat_date <= end,
        )
        if subject_id:
            stmt = stmt.where(DailyStatistics.subject_id == subject_id)
        return list(self.db.execute(stmt).scalars().all())

    def list_for_month(self, year: int, month: int) -> list[DailyStatistics]:
        stmt = select(DailyStatistics).where(
            DailyStatistics.stat_date >= date(year, month, 1),
            DailyStatistics.stat_date < (date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)),
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete_for_range(self, start: date, end: date) -> None:
        """Delete-and-rebuild strategy for recompute idempotency — see
        AnalyticsService.recompute_daily()."""
        stmt = select(DailyStatistics).where(DailyStatistics.stat_date >= start, DailyStatistics.stat_date <= end)
        for row in self.db.execute(stmt).scalars().all():
            self.db.delete(row)
        self.db.flush()

    def create(self, row: DailyStatistics) -> DailyStatistics:
        self.db.add(row)
        self.db.flush()
        return row

    def upsert(
        self, user_id: uuid.UUID, subject_id: uuid.UUID | None, stat_date: date,
        tests_taken: int, correct_answers: int, wrong_answers: int,
    ) -> DailyStatistics:
        """Sprint 64 — C6. AnalyticsService.recompute_daily() used to
        call create() in a loop after delete_for_range() (a
        delete-and-rebuild strategy). Two concurrent recomputes whose
        date windows overlap could both delete, both compute the same
        (user_id, subject_id, stat_date) bucket, and then race their
        plain INSERTs — the loser hitting an unhandled IntegrityError
        against uq_daily_statistics_user_subject_date instead of
        succeeding. A single INSERT ... ON CONFLICT DO UPDATE (mirroring
        AnswerRepository.upsert()'s established pattern) makes each
        bucket write atomic: Postgres itself resolves the conflict
        against that exact existing constraint, so the losing side
        becomes a graceful UPDATE instead of a crash, and re-running a
        recompute for the same window still converges to the same
        final counts (no double-counting) — the same intended semantics
        delete_for_range()+create() had, just race-safe.

        NOTE: subject_id is nullable, and Postgres does not treat two
        NULLs as equal for UNIQUE-constraint conflict detection — so
        two concurrent inserts for the same (user_id, NULL, stat_date)
        can still both succeed as separate rows despite ON CONFLICT
        (the constraint itself never fires). This is a pre-existing
        property of uq_daily_statistics_user_subject_date, not
        something this fix can close without a new migration (out of
        scope per this sprint's explicit no-new-migration rule); it
        already existed for the non-NULL-safe delete-then-create path
        too and is unchanged by this fix."""
        stmt = (
            pg_insert(DailyStatistics)
            .values(
                user_id=user_id, subject_id=subject_id, stat_date=stat_date,
                tests_taken=tests_taken, correct_answers=correct_answers, wrong_answers=wrong_answers,
            )
            .on_conflict_do_update(
                constraint="uq_daily_statistics_user_subject_date",
                set_={
                    "tests_taken": tests_taken, "correct_answers": correct_answers,
                    "wrong_answers": wrong_answers, "updated_at": func.now(),
                },
            )
        )
        self.db.execute(stmt)
        self.db.flush()
        return self.get(user_id, subject_id, stat_date)

    def commit(self) -> None:
        self.db.commit()


class MonthlyStatisticsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: uuid.UUID, subject_id: uuid.UUID | None, month: int, year: int) -> MonthlyStatistics | None:
        stmt = select(MonthlyStatistics).where(
            MonthlyStatistics.user_id == user_id, MonthlyStatistics.subject_id == subject_id,
            MonthlyStatistics.month == month, MonthlyStatistics.year == year,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID) -> list[MonthlyStatistics]:
        stmt = select(MonthlyStatistics).where(MonthlyStatistics.user_id == user_id)
        return list(self.db.execute(stmt).scalars().all())

    def upsert(self, user_id: uuid.UUID, subject_id: uuid.UUID | None, month: int, year: int, tests_taken: int, avg_score: float) -> MonthlyStatistics:
        """Sprint 64 — C6. Was get()-then-write (check-then-act): two
        concurrent recompute_monthly() calls for the same (user_id,
        subject_id, month, year) could both find no existing row via
        get(), both fall into the create() branch, and the loser's
        INSERT would raise an unhandled IntegrityError against
        uq_monthly_statistics_user_subject_month_year instead of
        updating the winning row. Converted to a single
        INSERT ... ON CONFLICT DO UPDATE — same established pattern as
        AnswerRepository.upsert() and this module's own new
        DailyStatisticsRepository.upsert() above — so the loser becomes
        a graceful UPDATE instead of a crash. Signature, return type and
        returned row's field values are unchanged from before this
        sprint; only the write is now atomic.

        NOTE: same NULL-subject_id caveat as DailyStatisticsRepository.
        upsert() above — Postgres doesn't treat two NULLs as a
        UNIQUE-constraint conflict, so this is a pre-existing property
        of uq_monthly_statistics_user_subject_month_year, unchanged by
        this fix, and not addressable without a new migration (out of
        this sprint's scope)."""
        stmt = (
            pg_insert(MonthlyStatistics)
            .values(user_id=user_id, subject_id=subject_id, month=month, year=year, tests_taken=tests_taken, avg_score=avg_score)
            .on_conflict_do_update(
                constraint="uq_monthly_statistics_user_subject_month_year",
                set_={"tests_taken": tests_taken, "avg_score": avg_score, "updated_at": func.now()},
            )
        )
        self.db.execute(stmt)
        self.db.flush()
        return self.get(user_id, subject_id, month, year)

    def commit(self) -> None:
        self.db.commit()
