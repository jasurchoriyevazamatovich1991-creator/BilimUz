"""
Business logic for role management. Roles are the load-bearing structure
behind every require_roles(...) check in the codebase — this service is
deliberately more protective than a typical CRUD module.
"""
import uuid

from app.core.audit import log_action
from app.modules.roles.constants import SYSTEM_ROLE_NAMES
from app.modules.roles.exceptions import (
    RoleAlreadyExistsException,
    RoleInUseException,
    RoleNotFoundException,
    SystemRoleProtectedException,
)
from app.modules.roles.models import Role
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import RoleCreateRequest, RoleListParams, RoleUpdateRequest


class RoleService:
    def __init__(self, repository: RoleRepository):
        self.repo = repository

    def get_role(self, role_id: uuid.UUID) -> Role:
        role = self.repo.get_by_id(role_id)
        if role is None:
            raise RoleNotFoundException("Rol topilmadi")
        return role

    def list_roles(self, params: RoleListParams) -> tuple[list[Role], int]:
        return self.repo.list(params)

    def create_role(self, data: RoleCreateRequest, actor_id: uuid.UUID) -> Role:
        if self.repo.get_by_name(data.name):
            raise RoleAlreadyExistsException("Bu nomdagi rol allaqachon mavjud")

        role = Role(name=data.name, description=data.description, created_by=actor_id)
        self.repo.create(role)
        log_action(self.repo.db, action="role.created", user_id=actor_id, entity_type="role", entity_id=role.id)
        self.repo.commit()
        return role

    def update_role(self, role_id: uuid.UUID, data: RoleUpdateRequest, actor_id: uuid.UUID) -> Role:
        role = self.get_role(role_id)
        updates = data.model_dump(exclude_unset=True)

        if role.name in SYSTEM_ROLE_NAMES and updates.get("status") not in (None, "active"):
            raise SystemRoleProtectedException(
                f"'{role.name}' — tizim roli, uni faolsizlantirib bo'lmaydi"
            )

        updates["updated_by"] = actor_id
        self.repo.update(role, updates)
        log_action(
            self.repo.db, action="role.updated", user_id=actor_id,
            entity_type="role", entity_id=role_id, metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return role

    def delete_role(self, role_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        role = self.get_role(role_id)
        if role.name in SYSTEM_ROLE_NAMES:
            raise SystemRoleProtectedException(
                f"'{role.name}' — tizim roli, uni o'chirib bo'lmaydi (faqat 'inactive' holatiga o'tkazish mumkin)"
            )
        users_count = self.repo.count_users_with_role(role_id)
        if users_count > 0:
            raise RoleInUseException(
                f"Bu rolga {users_count} ta foydalanuvchi biriktirilgan — avval ularni boshqa rolga o'tkazing"
            )

        self.repo.soft_delete(role)
        log_action(self.repo.db, action="role.deleted", user_id=actor_id, entity_type="role", entity_id=role_id)
        self.repo.commit()
