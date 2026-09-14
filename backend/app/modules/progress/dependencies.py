"""FastAPI dependency wiring for the progress module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.lessons.repository import LessonRepository
from app.modules.progress.repository import LessonProgressRepository
from app.modules.progress.service import ProgressService


def get_progress_repository(db: Session = Depends(get_db)) -> LessonProgressRepository:
    return LessonProgressRepository(db)


def get_progress_service(
    repo: LessonProgressRepository = Depends(get_progress_repository),
    db: Session = Depends(get_db),
) -> ProgressService:
    return ProgressService(repo, LessonRepository(db))
