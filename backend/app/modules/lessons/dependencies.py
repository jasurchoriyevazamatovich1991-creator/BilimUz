"""FastAPI dependency wiring for the lessons module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.lessons.repository import LessonRepository
from app.modules.lessons.service import LessonService
from app.modules.topics.repository import TopicRepository


def get_lesson_repository(db: Session = Depends(get_db)) -> LessonRepository:
    return LessonRepository(db)


def get_lesson_service(
    repo: LessonRepository = Depends(get_lesson_repository),
    db: Session = Depends(get_db),
) -> LessonService:
    return LessonService(repo, TopicRepository(db))
