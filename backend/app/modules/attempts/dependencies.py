"""FastAPI dependency wiring for the attempts module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.tests.repository import ExamModuleRepository, TestRepository


def get_attempt_repository(db: Session = Depends(get_db)) -> AttemptRepository:
    return AttemptRepository(db)


def get_answer_repository(db: Session = Depends(get_db)) -> AnswerRepository:
    return AnswerRepository(db)


def get_module_progress_repository(db: Session = Depends(get_db)) -> AttemptModuleProgressRepository:
    return AttemptModuleProgressRepository(db)


def get_exam_module_repository(db: Session = Depends(get_db)) -> ExamModuleRepository:
    return ExamModuleRepository(db)


def get_module_execution_service(
    module_repo: ExamModuleRepository = Depends(get_exam_module_repository),
    progress_repo: AttemptModuleProgressRepository = Depends(get_module_progress_repository),
    db: Session = Depends(get_db),
) -> ModuleExecutionService:
    return ModuleExecutionService(
        module_repo, progress_repo, QuestionRepository(db), AnswerRepository(db), AttemptRepository(db),
    )


def get_attempt_service(
    repo: AttemptRepository = Depends(get_attempt_repository),
    answer_repo: AnswerRepository = Depends(get_answer_repository),
    module_execution: ModuleExecutionService = Depends(get_module_execution_service),
    module_repo: ExamModuleRepository = Depends(get_exam_module_repository),
    db: Session = Depends(get_db),
) -> AttemptService:
    # Sprint 50 — module_execution/module_repo are now always wired for
    # the real FastAPI dependency path (production behavior). This is
    # exactly what makes AttemptService.start_attempt()'s has_modules()
    # branch actually activate for modular tests. Non-modular tests are
    # STILL completely unaffected — has_modules() returns False for
    # them, so the branch body never runs regardless of these being set.
    return AttemptService(
        repo, answer_repo, TestRepository(db), QuestionRepository(db), OptionRepository(db),
        module_execution, module_repo,
    )
