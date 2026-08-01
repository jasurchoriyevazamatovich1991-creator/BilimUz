"""Data-access layer. Only SQLAlchemy here — no business rules."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.grades.models import Grade
from app.modules.grades.schemas import GradeListParams


class GradeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, grade_id: uuid.UUID) -> Grade | None:
        stmt = select(Grade).where(Grade.id == grade_id, Grade.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name(self, name: str, exclude_id: uuid.UUID | None = None) -> Grade | None:
        stmt = select(Grade).where(func.lower(Grade.name) == name.lower(), Grade.deleted_at.is_(None))
        if exclude_id is not None:
            stmt = stmt.where(Grade.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: GradeListParams) -> tuple[list[Grade], int]:
        stmt = select(Grade).where(Grade.deleted_at.is_(None))
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = self._apply_sort(stmt, params.sort)
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: GradeListParams):
        if params.search:
            stmt = stmt.where(Grade.name.ilike(f"%{params.search}%"))
        if params.status:
            stmt = stmt.where(Grade.status == params.status)
        return stmt

    def _apply_sort(self, stmt, sort: str):
        descending = sort.startswith("-")
        field_name = sort.lstrip("-")
        column = getattr(Grade, field_name, Grade.name)
        return stmt.order_by(column.desc() if descending else column.asc())

    def create(self, grade: Grade) -> Grade:
        self.db.add(grade)
        self.db.flush()
        return grade

    def update(self, grade: Grade, data: dict) -> Grade:
        for field, value in data.items():
            setattr(grade, field, value)
        self.db.flush()
        return grade

    def soft_delete(self, grade: Grade) -> None:
        grade.deleted_at = datetime.now(timezone.utc)
        grade.status = "archived"
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
