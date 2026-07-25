"""
Auth-specific ORM models. `User` itself lives in app/users/models.py —
auth only owns the tables about the *act* of authenticating.
"""
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active | revoked


class LoginHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "login_history"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    device: Mapped[str | None] = mapped_column(String(150), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="logged")


class VerificationCode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "verification_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | used | expired


class PasswordHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores the last N password hashes per user (constants.PASSWORD_HISTORY_SIZE)
    so AuthService can reject reused passwords without ever storing plaintext."""
    __tablename__ = "password_history"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
