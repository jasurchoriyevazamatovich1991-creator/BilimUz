"""FastAPI dependency wiring for the analytics module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.analytics.repository import DailyStatisticsRepository, MonthlyStatisticsRepository
from app.modules.analytics.service import AnalyticsService
from app.modules.attempts.repository import AnswerRepository
from app.modules.results.repository import ResultRepository
from app.modules.tests.repository import TestRepository


def get_daily_repository(db: Session = Depends(get_db)) -> DailyStatisticsRepository:
    return DailyStatisticsRepository(db)


def get_monthly_repository(db: Session = Depends(get_db)) -> MonthlyStatisticsRepository:
    return MonthlyStatisticsRepository(db)


def get_analytics_service(
    daily_repo: DailyStatisticsRepository = Depends(get_daily_repository),
    monthly_repo: MonthlyStatisticsRepository = Depends(get_monthly_repository),
    db: Session = Depends(get_db),
) -> AnalyticsService:
    return AnalyticsService(daily_repo, monthly_repo, ResultRepository(db), AnswerRepository(db), TestRepository(db))
