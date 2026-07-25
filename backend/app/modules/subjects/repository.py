"""
Data-access layer. Owns query construction (filter/search/sort/pagination)
so the service layer stays free of SQLAlchemy syntax.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.subjects.models import Subject
from app.modules.subjects.schemas import SubjectListParams


class SubjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, subject_id: uuid.UUID) -> Subject | None:
        stmt = select(Subject).where(Subject.id == subject_id, Subject.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name(self, name: str, exclude_id: uuid.UUID | None = None) -> Subject | None:
        stmt = select(Subject).where(func.lower(Subject.name) == name.lower(), Subject.deleted_at.is_(None))
        if exclude_id is not None:
            stmt = stmt.where(Subject.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: SubjectListParams) -> tuple[list[Subject], int]:
        stmt = select(Subject).where(Subject.deleted_at.is_(None))
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = self._apply_sort(stmt, params.sort)
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: SubjectListParams):
        if params.search:
            stmt = stmt.where(Subject.name.ilike(f"%{params.search}%"))
        if params.status:
            stmt = stmt.where(Subject.status == params.status)
        return stmt

    def _apply_sort(self, stmt, sort: str):
        descending = sort.startswith("-")
        field_name = sort.lstrip("-")
        column = getattr(Subject, field_name, Subject.created_at)
        return stmt.order_by(column.desc() if descending else column.asc())

    def create(self, subject: Subject) -> Subject:
        self.db.add(subject)
        self.db.flush()
        return subject

    def update(self, subject: Subject, data: dict) -> Subject:
        for field, value in data.items():
            setattr(subject, field, value)
        self.db.flush()
        return subject

    def soft_delete(self, subject: Subject, deleted_by: uuid.UUID) -> None:
        from datetime import datetime, timezone
        subject.deleted_at = datetime.now(timezone.utc)
        subject.status = "archived"
        subject.updated_by = deleted_by
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
