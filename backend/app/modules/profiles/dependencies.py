"""FastAPI dependency wiring for the profiles module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.learning_centers.repository import LearningCenterRepository
from app.modules.profiles.repository import ProfileRepository
from app.modules.profiles.service import ProfileService
from app.modules.schools.repository import SchoolRepository
from app.modules.users.repository import UserRepository


def get_profile_repository(db: Session = Depends(get_db)) -> ProfileRepository:
    return ProfileRepository(db)


def get_profile_service(
    repo: ProfileRepository = Depends(get_profile_repository),
    db: Session = Depends(get_db),
) -> ProfileService:
    return ProfileService(repo, UserRepository(db), SchoolRepository(db), LearningCenterRepository(db))
