"""FastAPI dependency wiring for the attempts module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.attempts.repository import AnswerRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.tests.repository import TestRepository


def get_attempt_repository(db: Session = Depends(get_db)) -> AttemptRepository:
    return AttemptRepository(db)


def get_answer_repository(db: Session = Depends(get_db)) -> AnswerRepository:
    return AnswerRepository(db)


def get_attempt_service(
    repo: AttemptRepository = Depends(get_attempt_repository),
    answer_repo: AnswerRepository = Depends(get_answer_repository),
    db: Session = Depends(get_db),
) -> AttemptService:
    return AttemptService(repo, answer_repo, TestRepository(db), QuestionRepository(db), OptionRepository(db))
