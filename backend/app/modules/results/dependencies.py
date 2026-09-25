"""FastAPI dependency wiring for the results module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.attempts.dependencies import get_module_execution_service
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.questions.repository import QuestionRepository
from app.modules.results.repository import RankingRepository, ResultRepository, ResultSectionRepository, StatisticsRepository
from app.modules.results.service import RankingService, ResultService
from app.modules.tests.repository import ExamSectionRepository, TestRepository


def get_result_repository(db: Session = Depends(get_db)) -> ResultRepository:
    return ResultRepository(db)


def get_result_section_repository(db: Session = Depends(get_db)) -> ResultSectionRepository:
    return ResultSectionRepository(db)


def get_statistics_repository(db: Session = Depends(get_db)) -> StatisticsRepository:
    return StatisticsRepository(db)


def get_ranking_repository(db: Session = Depends(get_db)) -> RankingRepository:
    return RankingRepository(db)


def get_result_service(
    repo: ResultRepository = Depends(get_result_repository),
    stats_repo: StatisticsRepository = Depends(get_statistics_repository),
    section_repo: ResultSectionRepository = Depends(get_result_section_repository),
    # Sprint 63 — reuses the exact same ModuleExecutionService instance
    # AttemptService is wired with (get_module_execution_service is the
    # existing app/modules/attempts/dependencies.py factory), so
    # ResultService.get_result_detail() consults the identical Sprint 61
    # effective-question-scope algorithm rather than a second copy of it.
    module_execution_service: ModuleExecutionService = Depends(get_module_execution_service),
    db: Session = Depends(get_db),
) -> ResultService:
    return ResultService(
        repo, stats_repo, AttemptRepository(db), AnswerRepository(db), TestRepository(db), QuestionRepository(db),
        ExamSectionRepository(db), section_repo,
        module_execution_service=module_execution_service,
    )


def get_ranking_service(
    repo: RankingRepository = Depends(get_ranking_repository),
    result_repo: ResultRepository = Depends(get_result_repository),
    db: Session = Depends(get_db),
) -> RankingService:
    return RankingService(repo, result_repo, AttemptRepository(db))
