"""
Reusable SQLAlchemy mixins so every table follows the same DB rules:
UUID primary key, created_at/updated_at/deleted_at, created_by/updated_by
(audit trail), and status. See database/schema/schema_v2.sql for how the
created_by/updated_by foreign keys are wired without a circular-dependency
problem (users <-> roles) — same principle applies here: the FK constraint
to users.id is added by Alembic in a follow-up migration, not inline.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditMixin:
    """Who created/last-modified this row. Nullable — system-seeded rows
    (e.g. the first Super Admin, seed data) have no creator user."""
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class StatusMixin:
    """Generic lifecycle status for tables without a domain-specific status
    enum. Tables that already define their own `status` (e.g. users, tests,
    payments) should NOT use this mixin — they satisfy the rule directly."""
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

