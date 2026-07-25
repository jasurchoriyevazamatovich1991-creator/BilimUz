"""
FastAPI dependency wiring for the permissions module — including
require_permission(), the permission-based sibling of
auth.dependencies.require_roles(). Lives here (not in auth) because it
depends on RolePermissionService, which auth must not import (auth stays
independent of every other module, per ADR-005).
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.permissions.exceptions import PermissionDeniedException
from app.modules.permissions.repository import PermissionRepository, RolePermissionRepository
from app.modules.permissions.service import PermissionService, RolePermissionService
from app.modules.users.models import User


def get_permission_repository(db: Session = Depends(get_db)) -> PermissionRepository:
    return PermissionRepository(db)


def get_permission_service(repo: PermissionRepository = Depends(get_permission_repository)) -> PermissionService:
    return PermissionService(repo)


def get_role_permission_repository(db: Session = Depends(get_db)) -> RolePermissionRepository:
    return RolePermissionRepository(db)


def get_role_permission_service(
    rp_repo: RolePermissionRepository = Depends(get_role_permission_repository),
    p_repo: PermissionRepository = Depends(get_permission_repository),
) -> RolePermissionService:
    return RolePermissionService(rp_repo, p_repo)


def require_permission(code: str):
    """Usage: Depends(require_permission('CREATE_TEST'))

    Migration path from require_roles(): a router changes exactly one
    line, e.g. `Depends(require_roles('Admin', 'Super Admin'))` becomes
    `Depends(require_permission('SUBJECTS_MANAGE'))` — see
    docs/ADR/ADR-006-Use-RBAC.md. Both dependencies can coexist during
    migration; nothing forces an all-at-once switch.
    """

    def _check(
        user: User = Depends(get_current_user),
        service: RolePermissionService = Depends(get_role_permission_service),
    ) -> User:
        if not service.role_has_permission(user.role_id, code):
            raise PermissionDeniedException(f"'{code}' ruxsati talab qilinadi")
        return user

    return _check
