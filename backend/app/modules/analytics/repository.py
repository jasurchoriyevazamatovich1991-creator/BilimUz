"""Data-access layer for DailyStatistics, MonthlyStatistics — two
repositories in one file."""
import uuid
from datetime import date

from sqlalchemy import select
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
        existing = self.get(user_id, subject_id, month, year)
        if existing:
            existing.tests_taken = tests_taken
            existing.avg_score = avg_score
            self.db.flush()
            return existing
        row = MonthlyStatistics(user_id=user_id, subject_id=subject_id, month=month, year=year, tests_taken=tests_taken, avg_score=avg_score)
        self.db.add(row)
        self.db.flush()
        return row

    def commit(self) -> None:
        self.db.commit()
