"""FastAPI dependency wiring for the subjects module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.subjects.repository import SubjectRepository
from app.modules.subjects.service import SubjectService


def get_subject_repository(db: Session = Depends(get_db)) -> SubjectRepository:
    return SubjectRepository(db)


def get_subject_service(repo: SubjectRepository = Depends(get_subject_repository)) -> SubjectService:
    return SubjectService(repo)
