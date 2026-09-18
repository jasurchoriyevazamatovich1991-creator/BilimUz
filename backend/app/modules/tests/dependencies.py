"""FastAPI dependency wiring for the tests module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.grades.repository import GradeRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.tests.repository import ExamModuleRepository, ExamSectionRepository, TestRepository
from app.modules.tests.service import ExamModuleService, ExamSectionService, TestService
from app.modules.topics.repository import TopicRepository


def get_test_repository(db: Session = Depends(get_db)) -> TestRepository:
    return TestRepository(db)


def get_test_service(
    repo: TestRepository = Depends(get_test_repository),
    db: Session = Depends(get_db),
) -> TestService:
    return TestService(repo, SubjectRepository(db), GradeRepository(db), TopicRepository(db))


def get_exam_section_repository(db: Session = Depends(get_db)) -> ExamSectionRepository:
    return ExamSectionRepository(db)


def get_exam_module_repository(db: Session = Depends(get_db)) -> ExamModuleRepository:
    return ExamModuleRepository(db)


def get_exam_section_service(
    repo: ExamSectionRepository = Depends(get_exam_section_repository),
    test_repo: TestRepository = Depends(get_test_repository),
) -> ExamSectionService:
    return ExamSectionService(repo, test_repo)


def get_exam_module_service(
    repo: ExamModuleRepository = Depends(get_exam_module_repository),
    section_repo: ExamSectionRepository = Depends(get_exam_section_repository),
) -> ExamModuleService:
    return ExamModuleService(repo, section_repo)
