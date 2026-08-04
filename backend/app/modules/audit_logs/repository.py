"""
Data-access layer. Read-only — this module never writes to `audit_logs`
(that's core.audit.log_action()'s exclusive job, unchanged).

Does NOT filter by `deleted_at` — the `AuditLog` model (core/audit.py)
does not map that column (TimestampMixin only, no soft-delete mixin),
verified before writing this file. Filtering by an unmapped attribute
would raise an AttributeError, not silently no-op.
"""
import uuid
from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit_logs.models import AuditLog
from app.modules.audit_logs.schemas import AuditLogListParams


class AuditLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, log_id: uuid.UUID) -> AuditLog | None:
        stmt = select(AuditLog).where(AuditLog.id == log_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: AuditLogListParams) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog)
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(AuditLog.created_at.desc())
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: AuditLogListParams):
        if params.user_id:
            stmt = stmt.where(AuditLog.user_id == params.user_id)
        if params.action:
            stmt = stmt.where(AuditLog.action == params.action)
        if params.entity_type:
            stmt = stmt.where(AuditLog.entity_type == params.entity_type)
        if params.date_from:
            stmt = stmt.where(AuditLog.created_at >= datetime.combine(params.date_from, time.min, tzinfo=timezone.utc))
        if params.date_to:
            stmt = stmt.where(AuditLog.created_at <= datetime.combine(params.date_to, time.max, tzinfo=timezone.utc))
        return stmt
