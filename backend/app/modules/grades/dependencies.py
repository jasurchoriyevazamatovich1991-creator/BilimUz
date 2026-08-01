"""FastAPI dependency wiring for the grades module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.grades.repository import GradeRepository
from app.modules.grades.service import GradeService


def get_grade_repository(db: Session = Depends(get_db)) -> GradeRepository:
    return GradeRepository(db)


def get_grade_service(repo: GradeRepository = Depends(get_grade_repository)) -> GradeService:
    return GradeService(repo)
