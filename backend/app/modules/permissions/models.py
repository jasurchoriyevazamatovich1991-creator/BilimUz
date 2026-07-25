"""
Permission and RolePermission ORM models — mirrors `permissions` and
`role_permissions` tables in database/schema/schema_v2.sql (Module 4).
"""
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class Permission(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # e.g. CREATE_TEST
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class RolePermission(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    """
    Association table promoted to a full entity (id + audit + status)
    instead of a bare composite-PK junction — matches the trade-off
    documented in schema_v2.sql: gives a complete audit trail of *who
    granted which permission to which role and when*.
    """
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("permissions.id"), nullable=False)

    permission: Mapped["Permission"] = relationship(lazy="joined")
