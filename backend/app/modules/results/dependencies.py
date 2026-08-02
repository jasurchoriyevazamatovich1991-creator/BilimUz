"""FastAPI dependency wiring for the results module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.results.repository import RankingRepository, ResultRepository, StatisticsRepository
from app.modules.results.service import RankingService, ResultService
from app.modules.tests.repository import TestRepository


def get_result_repository(db: Session = Depends(get_db)) -> ResultRepository:
    return ResultRepository(db)


def get_statistics_repository(db: Session = Depends(get_db)) -> StatisticsRepository:
    return StatisticsRepository(db)


def get_ranking_repository(db: Session = Depends(get_db)) -> RankingRepository:
    return RankingRepository(db)


def get_result_service(
    repo: ResultRepository = Depends(get_result_repository),
    stats_repo: StatisticsRepository = Depends(get_statistics_repository),
    db: Session = Depends(get_db),
) -> ResultService:
    return ResultService(repo, stats_repo, AttemptRepository(db), AnswerRepository(db), TestRepository(db))


def get_ranking_service(
    repo: RankingRepository = Depends(get_ranking_repository),
    result_repo: ResultRepository = Depends(get_result_repository),
    db: Session = Depends(get_db),
) -> RankingService:
    return RankingService(repo, result_repo, AttemptRepository(db))
