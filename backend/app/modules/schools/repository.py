"""Data-access layer. Only SQLAlchemy here — no business rules."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.schools.models import School
from app.modules.schools.schemas import SchoolListParams


class SchoolRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, school_id: uuid.UUID) -> School | None:
        stmt = select(School).where(School.id == school_id, School.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: SchoolListParams) -> tuple[list[School], int]:
        stmt = select(School).where(School.deleted_at.is_(None))
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = self._apply_sort(stmt, params.sort)
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: SchoolListParams):
        if params.search:
            stmt = stmt.where(School.name.ilike(f"%{params.search}%"))
        if params.region:
            stmt = stmt.where(School.region == params.region)
        if params.district:
            stmt = stmt.where(School.district == params.district)
        if params.status:
            stmt = stmt.where(School.status == params.status)
        return stmt

    def _apply_sort(self, stmt, sort: str):
        descending = sort.startswith("-")
        field_name = sort.lstrip("-")
        column = getattr(School, field_name, School.name)
        return stmt.order_by(column.desc() if descending else column.asc())

    def create(self, school: School) -> School:
        self.db.add(school)
        self.db.flush()
        return school

    def update(self, school: School, data: dict) -> School:
        for field, value in data.items():
            setattr(school, field, value)
        self.db.flush()
        return school

    def soft_delete(self, school: School) -> None:
        school.deleted_at = datetime.now(timezone.utc)
        school.status = "archived"
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
