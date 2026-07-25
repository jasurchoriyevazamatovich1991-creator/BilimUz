"""
HTTP layer for /api/v1/roles/*. All endpoints require Admin or above —
the role list itself reveals the platform's privilege structure, so it's
never exposed publicly. Create/update/delete require Super Admin: creating
or modifying a role is a higher-privilege action than modifying a single
user, since it can affect every user later assigned to that role.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.modules.auth.dependencies import require_roles
from app.core.schemas import success_response
from app.modules.roles.dependencies import get_role_service
from app.modules.roles.schemas import RoleCreateRequest, RoleListParams, RoleOut, RoleUpdateRequest
from app.modules.roles.service import RoleService
from app.modules.users.models import User

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("")
def list_roles(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="name"),
    service: RoleService = Depends(get_role_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    params = RoleListParams(page=page, per_page=per_page, search=search, status=status_filter, sort=sort)
    items, total = service.list_roles(params)
    data = {
        "items": [RoleOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Rollar ro'yxati.")


@router.get("/{role_id}")
def get_role(
    role_id: uuid.UUID,
    service: RoleService = Depends(get_role_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    role = service.get_role(role_id)
    return success_response(RoleOut.model_validate(role), "Rol topildi.")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_role(
    data: RoleCreateRequest,
    service: RoleService = Depends(get_role_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    role = service.create_role(data, actor_id=admin.id)
    return success_response(RoleOut.model_validate(role), "Rol yaratildi.")


@router.patch("/{role_id}")
def update_role(
    role_id: uuid.UUID,
    data: RoleUpdateRequest,
    service: RoleService = Depends(get_role_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    role = service.update_role(role_id, data, actor_id=admin.id)
    return success_response(RoleOut.model_validate(role), "Rol yangilandi.")


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: uuid.UUID,
    service: RoleService = Depends(get_role_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    service.delete_role(role_id, actor_id=admin.id)
