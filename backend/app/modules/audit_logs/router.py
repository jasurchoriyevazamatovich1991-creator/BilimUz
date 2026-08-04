"""
HTTP layer for /api/v1/audit-logs/*. Read-only, Super Admin only — the
most sensitive read surface in the platform (can reveal every user's
actions across every module).
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.schemas import success_response
from app.modules.audit_logs.dependencies import get_audit_log_service
from app.modules.audit_logs.schemas import AuditLogListParams, AuditLogOut
from app.modules.audit_logs.service import AuditLogService
from app.modules.auth.dependencies import require_roles
from app.modules.users.models import User

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get(
    "",
    summary="List audit log entries",
    description="Filterable by user_id, action, entity_type, and date range (max 90 days). "
                "Super Admin only — this data can reveal every user's actions across every module.",
)
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None, description="Exact action name, e.g. 'test.created'"),
    entity_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    service: AuditLogService = Depends(get_audit_log_service),
    _admin: User = Depends(require_roles("Super Admin")),
):
    params = AuditLogListParams(
        page=page, per_page=per_page, user_id=user_id, action=action,
        entity_type=entity_type, date_from=date_from, date_to=date_to,
    )
    items, total = service.list_logs(params)
    data = {
        "items": [AuditLogOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Audit yozuvlari.")


@router.get(
    "/{log_id}",
    summary="Get an audit log entry by ID",
    description="Super Admin only.",
)
def get_audit_log(
    log_id: uuid.UUID,
    service: AuditLogService = Depends(get_audit_log_service),
    _admin: User = Depends(require_roles("Super Admin")),
):
    log = service.get_log(log_id)
    return success_response(AuditLogOut.model_validate(log), "Audit yozuvi.")
