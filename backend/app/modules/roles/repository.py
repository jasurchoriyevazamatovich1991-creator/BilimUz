"""Data-access layer. Only SQLAlchemy here — no business rules."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.roles.models import Role
from app.modules.roles.schemas import RoleListParams
from app.modules.users.models import User


class RoleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        stmt = select(Role).where(Role.id == role_id, Role.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name(self, name: str, exclude_id: uuid.UUID | None = None) -> Role | None:
        stmt = select(Role).where(func.lower(Role.name) == name.lower(), Role.deleted_at.is_(None))
        if exclude_id is not None:
            stmt = stmt.where(Role.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: RoleListParams) -> tuple[list[Role], int]:
        stmt = select(Role).where(Role.deleted_at.is_(None))
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = self._apply_sort(stmt, params.sort)
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: RoleListParams):
        if params.search:
            stmt = stmt.where(Role.name.ilike(f"%{params.search}%"))
        if params.status:
            stmt = stmt.where(Role.status == params.status)
        return stmt

    def _apply_sort(self, stmt, sort: str):
        descending = sort.startswith("-")
        field_name = sort.lstrip("-")
        column = getattr(Role, field_name, Role.name)
        return stmt.order_by(column.desc() if descending else column.asc())

    def count_users_with_role(self, role_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(User).where(
            User.role_id == role_id, User.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one()

    def create(self, role: Role) -> Role:
        self.db.add(role)
        self.db.flush()
        return role

    def update(self, role: Role, data: dict) -> Role:
        for field, value in data.items():
            setattr(role, field, value)
        self.db.flush()
        return role

    def soft_delete(self, role: Role) -> None:
        from datetime import datetime, timezone
        role.deleted_at = datetime.now(timezone.utc)
        role.status = "archived"
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
