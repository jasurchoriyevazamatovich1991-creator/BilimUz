"""FastAPI dependency wiring for the schools module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.schools.repository import SchoolRepository
from app.modules.schools.service import SchoolService


def get_school_repository(db: Session = Depends(get_db)) -> SchoolRepository:
    return SchoolRepository(db)


def get_school_service(repo: SchoolRepository = Depends(get_school_repository)) -> SchoolService:
    return SchoolService(repo)
