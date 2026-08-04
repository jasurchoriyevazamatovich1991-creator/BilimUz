"""FastAPI dependency wiring for the system_logs module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.system_logs.repository import SystemLogRepository
from app.modules.system_logs.service import SystemLogService


def get_system_log_repository(db: Session = Depends(get_db)) -> SystemLogRepository:
    return SystemLogRepository(db)


def get_system_log_service(repo: SystemLogRepository = Depends(get_system_log_repository)) -> SystemLogService:
    return SystemLogService(repo)
