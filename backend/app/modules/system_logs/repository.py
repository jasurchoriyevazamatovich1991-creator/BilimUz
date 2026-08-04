"""Data-access layer. Only SQLAlchemy here — no business rules.
No deleted_at filtering — SystemLog doesn't map that column (see
models.py docstring, matching AuditLog's precedent)."""
import uuid
from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.system_logs.models import SystemLog
from app.modules.system_logs.schemas import SystemLogListParams


class SystemLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, log_id: uuid.UUID) -> SystemLog | None:
        stmt = select(SystemLog).where(SystemLog.id == log_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: SystemLogListParams) -> tuple[list[SystemLog], int]:
        stmt = select(SystemLog)
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(SystemLog.created_at.desc())
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: SystemLogListParams):
        if params.level:
            stmt = stmt.where(SystemLog.level == params.level)
        if params.source:
            stmt = stmt.where(SystemLog.source == params.source)
        if params.date_from:
            stmt = stmt.where(SystemLog.created_at >= datetime.combine(params.date_from, time.min, tzinfo=timezone.utc))
        if params.date_to:
            stmt = stmt.where(SystemLog.created_at <= datetime.combine(params.date_to, time.max, tzinfo=timezone.utc))
        return stmt

    def create(self, log: SystemLog) -> SystemLog:
        self.db.add(log)
        self.db.flush()
        return log

    def commit(self) -> None:
        self.db.commit()
