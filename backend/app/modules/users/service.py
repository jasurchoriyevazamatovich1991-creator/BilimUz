"""
Business logic for user management. Note what's NOT here: registration,
login, password handling — those stay in `auth`. This module is about
*managing already-existing* users (profile edits, admin listing, role
assignment), not identity/credentials.
"""
import uuid

from app.core.audit import log_action
from app.core.exceptions import UserNotFoundException
from app.modules.users.exceptions import CannotModifySelfException
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserAdminUpdateRequest, UserListParams, UserSelfUpdateRequest


class UserService:
    def __init__(self, repository: UserRepository):
        self.repo = repository

    def get_user(self, user_id: uuid.UUID) -> User:
        user = self.repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException("Foydalanuvchi topilmadi")
        return user

    def list_users(self, params: UserListParams) -> tuple[list[User], int]:
        return self.repo.list(params)

    def update_own_profile(self, user_id: uuid.UUID, data: UserSelfUpdateRequest) -> User:
        user = self.get_user(user_id)
        updates = data.model_dump(exclude_unset=True)
        self.repo.update(user, updates)
        self.repo.commit()
        return user

    def admin_update_user(
        self, target_user_id: uuid.UUID, data: UserAdminUpdateRequest, actor_id: uuid.UUID
    ) -> User:
        if target_user_id == actor_id:
            raise CannotModifySelfException(
                "O'zingizni admin panel orqali tahrirlay olmaysiz — /users/me dan foydalaning"
            )
        user = self.get_user(target_user_id)
        updates = data.model_dump(exclude_unset=True)
        updates["updated_by"] = actor_id
        self.repo.update(user, updates)

        log_action(
            self.repo.db, action="user.admin_update", user_id=actor_id,
            entity_type="user", entity_id=target_user_id, metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return user

    def change_role(self, target_user_id: uuid.UUID, new_role_id: uuid.UUID, actor_id: uuid.UUID) -> User:
        """Super-Admin-only — enforced at the router layer (require_roles),
        not here. This method still refuses self-modification as defense
        in depth (a compromised Super Admin token shouldn't be able to
        silently demote itself to hide the compromise)."""
        if target_user_id == actor_id:
            raise CannotModifySelfException("O'z rolingizni o'zgartira olmaysiz")

        user = self.get_user(target_user_id)
        old_role_id = user.role_id
        self.repo.update(user, {"role_id": new_role_id, "updated_by": actor_id})

        log_action(
            self.repo.db, action="user.role_changed", user_id=actor_id,
            entity_type="user", entity_id=target_user_id,
            metadata={"old_role_id": str(old_role_id), "new_role_id": str(new_role_id)},
        )
        self.repo.commit()
        return user
