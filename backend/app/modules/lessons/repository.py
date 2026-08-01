"""Data-access layer. Only SQLAlchemy here — no business rules."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.lessons.models import Lesson
from app.modules.lessons.schemas import LessonListParams


class LessonRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, lesson_id: uuid.UUID) -> Lesson | None:
        stmt = select(Lesson).where(Lesson.id == lesson_id, Lesson.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: LessonListParams) -> tuple[list[Lesson], int]:
        stmt = select(Lesson).where(Lesson.deleted_at.is_(None))
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = self._apply_sort(stmt, params.sort)
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: LessonListParams):
        if params.search:
            stmt = stmt.where(Lesson.title.ilike(f"%{params.search}%"))
        if params.topic_id:
            stmt = stmt.where(Lesson.topic_id == params.topic_id)
        if params.status:
            stmt = stmt.where(Lesson.status == params.status)
        return stmt

    def _apply_sort(self, stmt, sort: str):
        descending = sort.startswith("-")
        field_name = sort.lstrip("-")
        column = getattr(Lesson, field_name, Lesson.created_at)
        return stmt.order_by(column.desc() if descending else column.asc())

    def create(self, lesson: Lesson) -> Lesson:
        self.db.add(lesson)
        self.db.flush()
        return lesson

    def update(self, lesson: Lesson, data: dict) -> Lesson:
        for field, value in data.items():
            setattr(lesson, field, value)
        self.db.flush()
        return lesson

    def soft_delete(self, lesson: Lesson) -> None:
        lesson.deleted_at = datetime.now(timezone.utc)
        lesson.status = "archived"
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
