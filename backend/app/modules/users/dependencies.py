"""FastAPI dependency wiring for the users module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_user_service(repo: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(repo)
