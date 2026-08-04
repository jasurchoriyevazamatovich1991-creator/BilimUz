"""Data-access layer. Only SQLAlchemy here — no business rules."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.profiles.models import Profile
from app.modules.profiles.schemas import ProfileListParams


class ProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: uuid.UUID) -> Profile | None:
        stmt = select(Profile).where(Profile.user_id == user_id, Profile.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, params: ProfileListParams) -> tuple[list[Profile], int]:
        stmt = select(Profile).where(Profile.deleted_at.is_(None))
        if params.school_id:
            stmt = stmt.where(Profile.school_id == params.school_id)
        if params.learning_center_id:
            stmt = stmt.where(Profile.learning_center_id == params.learning_center_id)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Profile.created_at.desc())
        stmt = stmt.offset((params.page - 1) * params.per_page).limit(params.per_page)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def create(self, profile: Profile) -> Profile:
        self.db.add(profile)
        self.db.flush()
        return profile

    def update(self, profile: Profile, data: dict) -> Profile:
        for field, value in data.items():
            setattr(profile, field, value)
        self.db.flush()
        return profile

    def commit(self) -> None:
        self.db.commit()
