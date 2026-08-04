"""Business logic for reading the audit trail. Read-only — no create/
update/delete methods exist in this service, by design (see module
docstrings in models.py/repository.py)."""
import uuid

from app.modules.audit_logs.exceptions import AuditLogNotFoundException
from app.modules.audit_logs.models import AuditLog
from app.modules.audit_logs.repository import AuditLogRepository
from app.modules.audit_logs.schemas import AuditLogListParams
from app.modules.audit_logs.validators import validate_date_range


class AuditLogService:
    def __init__(self, repository: AuditLogRepository):
        self.repo = repository

    def get_log(self, log_id: uuid.UUID) -> AuditLog:
        log = self.repo.get_by_id(log_id)
        if log is None:
            raise AuditLogNotFoundException("Audit yozuvi topilmadi")
        return log

    def list_logs(self, params: AuditLogListParams) -> tuple[list[AuditLog], int]:
        validate_date_range(params.date_from, params.date_to)
        return self.repo.list(params)
