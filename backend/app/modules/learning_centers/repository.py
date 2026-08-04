"""Data-access layer. Only SQLAlchemy here — no business rules."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.learning_centers.models import LearningCenter
from app.modules.learning_centers.schemas import LearningCenterListParams


class LearningCenterRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, center_id: uuid.UUID) -> LearningCenter | None:
        stmt = select(LearningCenter).where(LearningCenter.id == center_id, LearningCenter.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: LearningCenterListParams) -> tuple[list[LearningCenter], int]:
        stmt = select(LearningCenter).where(LearningCenter.deleted_at.is_(None))
        stmt = self._apply_filters(stmt, params)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = self._apply_sort(stmt, params.sort)
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def _apply_filters(self, stmt, params: LearningCenterListParams):
        if params.search:
            stmt = stmt.where(
                LearningCenter.name.ilike(f"%{params.search}%") | LearningCenter.owner_name.ilike(f"%{params.search}%")
            )
        if params.region:
            stmt = stmt.where(LearningCenter.region == params.region)
        if params.status:
            stmt = stmt.where(LearningCenter.status == params.status)
        return stmt

    def _apply_sort(self, stmt, sort: str):
        descending = sort.startswith("-")
        field_name = sort.lstrip("-")
        column = getattr(LearningCenter, field_name, LearningCenter.name)
        return stmt.order_by(column.desc() if descending else column.asc())

    def create(self, center: LearningCenter) -> LearningCenter:
        self.db.add(center)
        self.db.flush()
        return center

    def update(self, center: LearningCenter, data: dict) -> LearningCenter:
        for field, value in data.items():
            setattr(center, field, value)
        self.db.flush()
        return center

    def soft_delete(self, center: LearningCenter) -> None:
        center.deleted_at = datetime.now(timezone.utc)
        center.status = "archived"
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
