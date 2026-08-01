"""Data-access layer. Only SQLAlchemy here — no business rules."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.topics.models import Topic
from app.modules.topics.schemas import TopicListParams


class TopicRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, topic_id: uuid.UUID) -> Topic | None:
        stmt = select(Topic).where(Topic.id == topic_id, Topic.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: TopicListParams) -> tuple[list[Topic], int]:
        stmt = select(Topic).where(Topic.deleted_at.is_(None))
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = self._apply_sort(stmt, params.sort)
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: TopicListParams):
        if params.search:
            stmt = stmt.where(Topic.title.ilike(f"%{params.search}%"))
        if params.subject_id:
            stmt = stmt.where(Topic.subject_id == params.subject_id)
        if params.grade_id:
            stmt = stmt.where(Topic.grade_id == params.grade_id)
        if params.status:
            stmt = stmt.where(Topic.status == params.status)
        return stmt

    def _apply_sort(self, stmt, sort: str):
        descending = sort.startswith("-")
        field_name = sort.lstrip("-")
        column = getattr(Topic, field_name, Topic.order_number)
        return stmt.order_by(column.desc() if descending else column.asc())

    def create(self, topic: Topic) -> Topic:
        self.db.add(topic)
        self.db.flush()
        return topic

    def update(self, topic: Topic, data: dict) -> Topic:
        for field, value in data.items():
            setattr(topic, field, value)
        self.db.flush()
        return topic

    def soft_delete(self, topic: Topic) -> None:
        topic.deleted_at = datetime.now(timezone.utc)
        topic.status = "archived"
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
