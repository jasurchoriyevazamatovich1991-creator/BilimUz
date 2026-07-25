"""
HTTP layer for /api/v1/users/*. Role reassignment is deliberately
'Super Admin' only, not 'Admin' — an ordinary Admin must not be able to
grant themselves or anyone else Super Admin (privilege escalation).
"""
import uuid

from fastapi import APIRouter, Depends, Query

from app.modules.auth.dependencies import get_current_user, require_roles
from app.core.schemas import success_response
from app.modules.users.dependencies import get_user_service
from app.modules.users.schemas import (
    UserAdminUpdateRequest,
    UserListParams,
    UserOut,
    UserRoleChangeRequest,
    UserSelfUpdateRequest,
)
from app.modules.users.service import UserService
from app.modules.users.models import User

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
def get_my_profile(current_user: User = Depends(get_current_user)):
    return success_response(UserOut.model_validate(current_user), "Mening profilim.")


@router.patch("/me")
def update_my_profile(
    data: UserSelfUpdateRequest,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
):
    user = service.update_own_profile(current_user.id, data)
    return success_response(UserOut.model_validate(user), "Profil yangilandi.")


@router.get("")
def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    role_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="-created_at"),
    service: UserService = Depends(get_user_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    params = UserListParams(page=page, per_page=per_page, search=search, role_id=role_id, status=status_filter, sort=sort)
    items, total = service.list_users(params)
    data = {
        "items": [UserOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Foydalanuvchilar ro'yxati.")


@router.get("/{user_id}")
def get_user(
    user_id: uuid.UUID,
    service: UserService = Depends(get_user_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    user = service.get_user(user_id)
    return success_response(UserOut.model_validate(user), "Foydalanuvchi topildi.")


@router.patch("/{user_id}")
def admin_update_user(
    user_id: uuid.UUID,
    data: UserAdminUpdateRequest,
    service: UserService = Depends(get_user_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    user = service.admin_update_user(user_id, data, actor_id=admin.id)
    return success_response(UserOut.model_validate(user), "Foydalanuvchi yangilandi.")


@router.patch("/{user_id}/role")
def change_user_role(
    user_id: uuid.UUID,
    data: UserRoleChangeRequest,
    service: UserService = Depends(get_user_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    user = service.change_role(user_id, data.role_id, actor_id=admin.id)
    return success_response(UserOut.model_validate(user), "Rol o'zgartirildi.")
