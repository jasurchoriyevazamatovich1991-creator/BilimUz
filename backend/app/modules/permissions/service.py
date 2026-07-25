"""
Business logic for permission management AND the core RBAC check itself
(role_has_permission). This is the module ADR-006 promised: permission
checks become additive on top of the existing roles/role_permissions
schema, with zero migration needed.
"""
import uuid

from app.core.audit import log_action
from app.modules.permissions.exceptions import (
    PermissionAlreadyExistsException,
    PermissionNotFoundException,
    RolePermissionAlreadyExistsException,
    RolePermissionNotFoundException,
)
from app.modules.permissions.models import Permission, RolePermission
from app.modules.permissions.repository import PermissionRepository, RolePermissionRepository
from app.modules.permissions.schemas import PermissionCreateRequest, PermissionListParams, PermissionUpdateRequest


class PermissionService:
    def __init__(self, repository: PermissionRepository):
        self.repo = repository

    def get_permission(self, permission_id: uuid.UUID) -> Permission:
        permission = self.repo.get_by_id(permission_id)
        if permission is None:
            raise PermissionNotFoundException("Ruxsat topilmadi")
        return permission

    def list_permissions(self, params: PermissionListParams) -> tuple[list[Permission], int]:
        return self.repo.list(params)

    def create_permission(self, data: PermissionCreateRequest, actor_id: uuid.UUID) -> Permission:
        if self.repo.get_by_code(data.code):
            raise PermissionAlreadyExistsException(f"'{data.code}' kodli ruxsat allaqachon mavjud")

        permission = Permission(
            name=data.name, code=data.code, module=data.module,
            description=data.description, created_by=actor_id,
        )
        self.repo.create(permission)
        log_action(self.repo.db, action="permission.created", user_id=actor_id, entity_type="permission", entity_id=permission.id)
        self.repo.commit()
        return permission

    def update_permission(self, permission_id: uuid.UUID, data: PermissionUpdateRequest, actor_id: uuid.UUID) -> Permission:
        permission = self.get_permission(permission_id)
        updates = data.model_dump(exclude_unset=True)
        updates["updated_by"] = actor_id
        self.repo.update(permission, updates)
        log_action(
            self.repo.db, action="permission.updated", user_id=actor_id,
            entity_type="permission", entity_id=permission_id, metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return permission

    def delete_permission(self, permission_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        permission = self.get_permission(permission_id)
        self.repo.soft_delete(permission)
        log_action(self.repo.db, action="permission.deleted", user_id=actor_id, entity_type="permission", entity_id=permission_id)
        self.repo.commit()


class RolePermissionService:
    def __init__(self, repository: RolePermissionRepository, permission_repository: PermissionRepository):
        self.repo = repository
        self.permission_repo = permission_repository

    def list_for_role(self, role_id: uuid.UUID) -> list[RolePermission]:
        return self.repo.list_for_role(role_id)

    def assign(self, role_id: uuid.UUID, permission_id: uuid.UUID, actor_id: uuid.UUID) -> RolePermission:
        if self.permission_repo.get_by_id(permission_id) is None:
            raise PermissionNotFoundException("Ruxsat topilmadi")
        if self.repo.get(role_id, permission_id):
            raise RolePermissionAlreadyExistsException("Bu ruxsat allaqachon shu rolga biriktirilgan")

        grant = RolePermission(role_id=role_id, permission_id=permission_id, created_by=actor_id)
        self.repo.create(grant)
        log_action(
            self.repo.db, action="role_permission.granted", user_id=actor_id,
            entity_type="role", entity_id=role_id, metadata={"permission_id": str(permission_id)},
        )
        self.repo.commit()
        return grant

    def revoke(self, role_id: uuid.UUID, permission_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        grant = self.repo.get(role_id, permission_id)
        if grant is None:
            raise RolePermissionNotFoundException("Bu rolga bu ruxsat biriktirilmagan")

        self.repo.soft_delete(grant)
        log_action(
            self.repo.db, action="role_permission.revoked", user_id=actor_id,
            entity_type="role", entity_id=role_id, metadata={"permission_id": str(permission_id)},
        )
        self.repo.commit()

    def role_has_permission(self, role_id: uuid.UUID, code: str) -> bool:
        """The function require_permission() (auth-adjacent dependency)
        calls on every protected request. Kept here, not duplicated, so
        there is exactly one place that answers 'can this role do X'."""
        return self.repo.role_has_permission_code(role_id, code)
