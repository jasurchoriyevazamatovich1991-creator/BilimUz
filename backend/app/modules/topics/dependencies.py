"""FastAPI dependency wiring for the topics module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.grades.repository import GradeRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.topics.repository import TopicRepository
from app.modules.topics.service import TopicService


def get_topic_repository(db: Session = Depends(get_db)) -> TopicRepository:
    return TopicRepository(db)


def get_topic_service(
    repo: TopicRepository = Depends(get_topic_repository),
    db: Session = Depends(get_db),
) -> TopicService:
    return TopicService(repo, SubjectRepository(db), GradeRepository(db))
