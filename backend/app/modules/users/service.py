"""
Business logic for user management. Note what's NOT here: registration,
login, password handling — those stay in `auth`. This module is about
*managing already-existing* users (profile edits, admin listing, role
assignment), not identity/credentials.
"""
import uuid

from sqlalchemy import or_, select

from app.core.audit import log_action
from app.core.exceptions import AppException, UserAlreadyExistsException, UserNotFoundException
from app.core.security.password_service import PasswordService
from app.modules.auth.models import PasswordHistory
from app.modules.roles.models import Role
from app.modules.users.constants import CREATABLE_ROLES_BY_ACTOR
from app.modules.users.exceptions import CannotModifySelfException
from app.modules.users.models import User, UserStatus
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserAdminUpdateRequest, UserCreateRequest, UserListParams, UserSelfUpdateRequest


class RoleNotAssignableException(AppException):
    status_code = 403
    error_code = "ROLE_NOT_ASSIGNABLE"


class UserService:
    def __init__(self, repository: UserRepository):
        self.repo = repository

    def get_user(self, user_id: uuid.UUID) -> User:
        user = self.repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException("Foydalanuvchi topilmadi")
        return user

    def create_user(self, data: UserCreateRequest, actor: User) -> User:
        """Task 10.1 — administrator-managed account creation. The new account
        is 'active' (the administrator vouches for it; no OTP is involved).
        Duplicates are checked across ALL users, including soft-deleted ones,
        because phone/email are unique in the table."""
        allowed = CREATABLE_ROLES_BY_ACTOR.get(actor.role.name, ())
        if data.role not in allowed:
            raise RoleNotAssignableException(
                f"Siz faqat quyidagi rollarda foydalanuvchi yarata olasiz: {', '.join(allowed) or '—'}"
            )
        role = self.repo.db.execute(select(Role).where(Role.name == data.role)).scalar_one_or_none()
        if role is None:
            raise RoleNotAssignableException("Rol topilmadi")
        clash = [User.phone == data.phone] + ([User.email == data.email] if data.email else [])
        if self.repo.db.execute(select(User.id).where(or_(*clash))).first() is not None:
            raise UserAlreadyExistsException("Bu telefon yoki email allaqachon ro'yxatdan o'tgan")

        password_hash = PasswordService().hash_password(data.password)
        user = User(
            role_id=role.id, first_name=data.first_name, last_name=data.last_name,
            phone=data.phone, email=data.email, password_hash=password_hash,
            status=UserStatus.ACTIVE, created_by=actor.id, updated_by=actor.id,
        )
        self.repo.db.add(user)
        self.repo.db.flush()
        self.repo.db.add(PasswordHistory(user_id=user.id, password_hash=password_hash))
        log_action(self.repo.db, action="user.created_by_admin", user_id=actor.id,
                   entity_type="user", entity_id=user.id, metadata={"role": data.role})
        self.repo.commit()
        self.repo.db.refresh(user)
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
