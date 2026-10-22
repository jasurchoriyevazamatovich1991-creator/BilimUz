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


# Task 10 / 10.1 — statuses that must not authenticate (login, token
# refresh, or any request with a still-valid access token). Task 10.1 adds
# 'pending_verification': an account whose phone was never verified must
# not get access (public registration is disabled; administrators create
# accounts as 'active' — see users/service.create_user).
DISABLED_USER_STATUSES = frozenset({UserStatus.INACTIVE.value, UserStatus.BANNED.value, UserStatus.PENDING_VERIFICATION.value})

_BLOCK_MESSAGES = {
    UserStatus.INACTIVE.value: "Akkaunt faol emas",
    UserStatus.BANNED.value: "Akkaunt faol emas",
    UserStatus.PENDING_VERIFICATION.value: "Akkaunt hali tasdiqlanmagan",
}


def _status_value(user):
    status = getattr(user, "status", None)
    return status.value if isinstance(status, UserStatus) else status


def is_user_disabled(user) -> bool:
    return _status_value(user) in DISABLED_USER_STATUSES


def account_block_message(user) -> str:
    return _BLOCK_MESSAGES.get(_status_value(user), "Akkaunt faol emas")


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
