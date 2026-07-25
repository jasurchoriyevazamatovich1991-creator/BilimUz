"""
HTTP layer for /api/v1/permissions/*. Two resource groups in one router:
the permission catalog itself, and role<->permission grants — both
Super-Admin-only to create/modify, since misconfiguring either directly
changes what every user with that role can do platform-wide.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.permissions.dependencies import (
    get_permission_service,
    get_role_permission_service,
)
from app.modules.permissions.schemas import (
    PermissionCreateRequest,
    PermissionListParams,
    PermissionOut,
    PermissionUpdateRequest,
    RolePermissionAssignRequest,
    RolePermissionOut,
)
from app.modules.permissions.service import PermissionService, RolePermissionService
from app.modules.users.models import User

router = APIRouter(prefix="/permissions", tags=["Permissions"])


@router.get("")
def list_permissions(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    module: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="module"),
    service: PermissionService = Depends(get_permission_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    params = PermissionListParams(page=page, per_page=per_page, search=search, module=module, status=status_filter, sort=sort)
    items, total = service.list_permissions(params)
    data = {
        "items": [PermissionOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Ruxsatlar ro'yxati.")


@router.get("/{permission_id}")
def get_permission(
    permission_id: uuid.UUID,
    service: PermissionService = Depends(get_permission_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    permission = service.get_permission(permission_id)
    return success_response(PermissionOut.model_validate(permission), "Ruxsat topildi.")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_permission(
    data: PermissionCreateRequest,
    service: PermissionService = Depends(get_permission_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    permission = service.create_permission(data, actor_id=admin.id)
    return success_response(PermissionOut.model_validate(permission), "Ruxsat yaratildi.")


@router.patch("/{permission_id}")
def update_permission(
    permission_id: uuid.UUID,
    data: PermissionUpdateRequest,
    service: PermissionService = Depends(get_permission_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    permission = service.update_permission(permission_id, data, actor_id=admin.id)
    return success_response(PermissionOut.model_validate(permission), "Ruxsat yangilandi.")


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_permission(
    permission_id: uuid.UUID,
    service: PermissionService = Depends(get_permission_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    service.delete_permission(permission_id, actor_id=admin.id)


@router.get("/roles/{role_id}")
def list_role_permissions(
    role_id: uuid.UUID,
    service: RolePermissionService = Depends(get_role_permission_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    grants = service.list_for_role(role_id)
    return success_response([RolePermissionOut.model_validate(g) for g in grants], "Rolga biriktirilgan ruxsatlar.")


@router.post("/roles/{role_id}/assign", status_code=status.HTTP_201_CREATED)
def assign_permission(
    role_id: uuid.UUID,
    data: RolePermissionAssignRequest,
    service: RolePermissionService = Depends(get_role_permission_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    grant = service.assign(role_id, data.permission_id, actor_id=admin.id)
    return success_response(RolePermissionOut.model_validate(grant), "Ruxsat rolga biriktirildi.")


@router.delete("/roles/{role_id}/revoke/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_permission(
    role_id: uuid.UUID,
    permission_id: uuid.UUID,
    service: RolePermissionService = Depends(get_role_permission_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    service.revoke(role_id, permission_id, actor_id=admin.id)
