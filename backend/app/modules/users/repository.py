"""Data-access layer. Only SQLAlchemy here — no business rules."""
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.users.schemas import UserListParams


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: UserListParams) -> tuple[list[User], int]:
        stmt = select(User).where(User.deleted_at.is_(None))
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = self._apply_sort(stmt, params.sort)
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: UserListParams):
        if params.search:
            like = f"%{params.search}%"
            stmt = stmt.where(
                or_(User.first_name.ilike(like), User.last_name.ilike(like),
                    User.email.ilike(like), User.phone.ilike(like))
            )
        if params.role_id:
            stmt = stmt.where(User.role_id == params.role_id)
        if params.status:
            stmt = stmt.where(User.status == params.status)
        return stmt

    def _apply_sort(self, stmt, sort: str):
        descending = sort.startswith("-")
        field_name = sort.lstrip("-")
        column = getattr(User, field_name, User.created_at)
        return stmt.order_by(column.desc() if descending else column.asc())

    def update(self, user: User, data: dict) -> User:
        for field, value in data.items():
            setattr(user, field, value)
        self.db.flush()
        return user

    def commit(self) -> None:
        self.db.commit()
