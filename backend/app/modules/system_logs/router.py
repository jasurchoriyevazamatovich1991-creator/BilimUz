"""
HTTP layer for /api/v1/system-logs/*. Super Admin only, for both read
and write (approved decision) — system-level messages can contain
internal details (stack traces, file paths) that shouldn't be broadly
visible, consistent with the platform-wide rule that internal errors
never reach a client response.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.system_logs.dependencies import get_system_log_service
from app.modules.system_logs.schemas import CreateSystemLogRequest, SystemLogListParams, SystemLogOut
from app.modules.system_logs.service import SystemLogService
from app.modules.users.models import User

router = APIRouter(prefix="/system-logs", tags=["System Logs"])


@router.get(
    "",
    summary="List system log entries",
    description="Filterable by level, source, and date range (max 90 days). Super Admin only. "
                "Note: this table has no producers yet in this sprint — core/logging.py still writes "
                "to stdout only; wiring it to call this module's create_log() is future work.",
)
def list_system_logs(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    level: str | None = Query(default=None, description="info, warning, error, or critical"),
    source: str | None = Query(default=None),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    service: SystemLogService = Depends(get_system_log_service),
    _admin: User = Depends(require_roles("Super Admin")),
):
    params = SystemLogListParams(page=page, per_page=per_page, level=level, source=source, date_from=date_from, date_to=date_to)
    items, total = service.list_logs(params)
    data = {
        "items": [SystemLogOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Tizim yozuvlari.")


@router.get(
    "/{log_id}",
    summary="Get a system log entry by ID",
    description="Super Admin only.",
)
def get_system_log(
    log_id: uuid.UUID,
    service: SystemLogService = Depends(get_system_log_service),
    _admin: User = Depends(require_roles("Super Admin")),
):
    log = service.get_log(log_id)
    return success_response(SystemLogOut.model_validate(log), "Tizim yozuvi.")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Record a system-level event",
    description="Manual incident recording. Super Admin only. level must be one of: "
                "info, warning, error, critical.",
)
def create_system_log(
    data: CreateSystemLogRequest,
    service: SystemLogService = Depends(get_system_log_service),
    _admin: User = Depends(require_roles("Super Admin")),
):
    log = service.create_log(data.level, data.message, data.source, data.context)
    return success_response(SystemLogOut.model_validate(log), "Tizim yozuvi qo'shildi.")
