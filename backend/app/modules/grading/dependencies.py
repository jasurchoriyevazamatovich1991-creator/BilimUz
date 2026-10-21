"""Task 5 — FastAPI wiring for the grading module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.attempts.dependencies import get_module_execution_service
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.grading.repository import GradingQueueRepository, ReviewRepository, RubricRepository
from app.modules.grading.service import GradingService, RubricService
from app.modules.questions.repository import QuestionRepository
from app.modules.results.dependencies import get_result_service
from app.modules.results.service import ResultService
from app.modules.tests.repository import ExamSectionRepository, TestRepository


def get_rubric_service(db: Session = Depends(get_db)) -> RubricService:
    return RubricService(RubricRepository(db))


def get_grading_service(
    db: Session = Depends(get_db),
    module_execution: ModuleExecutionService = Depends(get_module_execution_service),
    result_service: ResultService = Depends(get_result_service),
) -> GradingService:
    return GradingService(
        RubricRepository(db), ReviewRepository(db), GradingQueueRepository(db), AttemptRepository(db),
        AnswerRepository(db), QuestionRepository(db), ExamSectionRepository(db), TestRepository(db),
        module_execution, result_service,
    )
