"""
Data-access layer for Result, Statistics, Ranking — three repositories
in one file, same cohesive-module reasoning as questions/repository.py
and permissions/repository.py.
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.results.models import Ranking, Result, Statistics


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
