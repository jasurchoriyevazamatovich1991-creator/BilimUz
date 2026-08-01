"""FastAPI dependency wiring for the tests module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.grades.repository import GradeRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.tests.repository import TestRepository
from app.modules.tests.service import TestService
from app.modules.topics.repository import TopicRepository


def get_test_repository(db: Session = Depends(get_db)) -> TestRepository:
    return TestRepository(db)


def get_test_service(
    repo: TestRepository = Depends(get_test_repository),
    db: Session = Depends(get_db),
) -> TestService:
    return TestService(repo, SubjectRepository(db), GradeRepository(db), TopicRepository(db))
