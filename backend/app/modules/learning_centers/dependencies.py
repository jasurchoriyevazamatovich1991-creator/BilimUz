"""FastAPI dependency wiring for the learning_centers module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.learning_centers.repository import LearningCenterRepository
from app.modules.learning_centers.service import LearningCenterService


def get_learning_center_repository(db: Session = Depends(get_db)) -> LearningCenterRepository:
    return LearningCenterRepository(db)


def get_learning_center_service(repo: LearningCenterRepository = Depends(get_learning_center_repository)) -> LearningCenterService:
    return LearningCenterService(repo)
