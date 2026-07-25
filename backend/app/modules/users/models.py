"""User ORM model — the identity record every other module references."""
import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.mixins import AuditMixin, TimestampMixin, UUIDPrimaryKeyMixin


class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"
    PENDING_VERIFICATION = "pending_verification"


class UserGender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin):
    __tablename__ = "users"
    __table_args__ = (
        {"comment": "Central identity table — every other module references this via user_id."},
    )

    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    gender: Mapped[UserGender | None] = mapped_column(String(10), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        String(30), nullable=False, default=UserStatus.PENDING_VERIFICATION
    )

    role: Mapped["Role"] = relationship(back_populates="users")
