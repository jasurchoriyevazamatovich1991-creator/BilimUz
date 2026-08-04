"""
Business logic for system logs. `create_log()` is designed to be
importable and callable directly (same calling convention as
core.audit.log_action()) so a FUTURE sprint can wire core/logging.py to
call it on WARNING+ events without going through HTTP. That wiring is
explicitly NOT done this sprint — core/logging.py is not modified
(Architecture Freeze: don't touch stable core infrastructure without a
specific, approved reason).
"""
import uuid

from app.modules.system_logs.exceptions import SystemLogNotFoundException
from app.modules.system_logs.models import SystemLog
from app.modules.system_logs.repository import SystemLogRepository
from app.modules.system_logs.schemas import SystemLogListParams
from app.modules.system_logs.validators import validate_date_range


class SystemLogService:
    def __init__(self, repository: SystemLogRepository):
        self.repo = repository

    def create_log(self, level: str, message: str, source: str | None = None, context: dict | None = None) -> SystemLog:
        log = SystemLog(level=level, source=source, message=message, context=context)
        self.repo.create(log)
        self.repo.commit()
        return log

    def get_log(self, log_id: uuid.UUID) -> SystemLog:
        log = self.repo.get_by_id(log_id)
        if log is None:
            raise SystemLogNotFoundException("Tizim yozuvi topilmadi")
        return log

    def list_logs(self, params: SystemLogListParams) -> tuple[list[SystemLog], int]:
        validate_date_range(params.date_from, params.date_to)
        return self.repo.list(params)
