"""
Data-access layer for both `permissions` and `role_permissions` — two
repositories in one file since they're a single cohesive concern (a
permission with no grants is meaningless, a grant with no permission is
impossible), matching how they're grouped as one module in the schema.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.permissions.models import Permission, RolePermission
from app.modules.permissions.schemas import PermissionListParams


class PermissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, permission_id: uuid.UUID) -> Permission | None:
        stmt = select(Permission).where(Permission.id == permission_id, Permission.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_code(self, code: str) -> Permission | None:
        stmt = select(Permission).where(Permission.code == code, Permission.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: PermissionListParams) -> tuple[list[Permission], int]:
        stmt = select(Permission).where(Permission.deleted_at.is_(None))
        if params.search:
            stmt = stmt.where(Permission.name.ilike(f"%{params.search}%"))
        if params.module:
            stmt = stmt.where(Permission.module == params.module)
        if params.status:
            stmt = stmt.where(Permission.status == params.status)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        descending = params.sort.startswith("-")
        field_name = params.sort.lstrip("-")
        column = getattr(Permission, field_name, Permission.module)
        stmt = stmt.order_by(column.desc() if descending else column.asc())
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def create(self, permission: Permission) -> Permission:
        self.db.add(permission)
        self.db.flush()
        return permission

    def update(self, permission: Permission, data: dict) -> Permission:
        for field, value in data.items():
            setattr(permission, field, value)
        self.db.flush()
        return permission

    def soft_delete(self, permission: Permission) -> None:
        from datetime import datetime, timezone
        permission.deleted_at = datetime.now(timezone.utc)
        permission.status = "archived"
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()


class RolePermissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, role_id: uuid.UUID, permission_id: uuid.UUID) -> RolePermission | None:
        stmt = select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
            RolePermission.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_role(self, role_id: uuid.UUID) -> list[RolePermission]:
        stmt = (
            select(RolePermission)
            .where(RolePermission.role_id == role_id, RolePermission.deleted_at.is_(None))
            .options(selectinload(RolePermission.permission))
        )
        return list(self.db.execute(stmt).scalars().all())

    def role_has_permission_code(self, role_id: uuid.UUID, code: str) -> bool:
        """The single query require_permission() depends on — kept as one
        indexed join so the RBAC check stays fast even at 'millions of
        users' scale (idx_role_permissions_role_id + uq_permissions_code)."""
        stmt = (
            select(RolePermission.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                RolePermission.role_id == role_id,
                RolePermission.deleted_at.is_(None),
                RolePermission.status == "active",
                Permission.code == code,
                Permission.deleted_at.is_(None),
                Permission.status == "active",
            )
        )
        return self.db.execute(stmt).first() is not None

    def create(self, role_permission: RolePermission) -> RolePermission:
        self.db.add(role_permission)
        self.db.flush()
        return role_permission

    def soft_delete(self, role_permission: RolePermission) -> None:
        from datetime import datetime, timezone
        role_permission.deleted_at = datetime.now(timezone.utc)
        role_permission.status = "archived"
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
