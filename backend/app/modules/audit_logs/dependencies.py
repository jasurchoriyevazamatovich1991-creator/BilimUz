"""FastAPI dependency wiring for the audit_logs module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.audit_logs.repository import AuditLogRepository
from app.modules.audit_logs.service import AuditLogService


def get_audit_log_repository(db: Session = Depends(get_db)) -> AuditLogRepository:
    return AuditLogRepository(db)


def get_audit_log_service(repo: AuditLogRepository = Depends(get_audit_log_repository)) -> AuditLogService:
    return AuditLogService(repo)
