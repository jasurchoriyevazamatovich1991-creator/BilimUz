"""
SystemLog ORM model — mirrors `system_logs` table in schema_v2.sql
(Module 25). Unlike `audit_logs`, this table has never been written to
by anything in the codebase (`core/logging.py` writes to stdout only) —
this is a genuinely new model, not a reuse.

No created_by/updated_by (verified against schema_v2.sql) — no
AuditMixin. `status` defaults to 'logged' (not the generic 'active'),
matching the same direct-column pattern already used by `AuditLog`
(core/audit.py) for consistency between the two "logs" models — not
using StatusMixin here either, same reasoning.

deleted_at is NOT mapped, mirroring AuditLog's precedent exactly — a
log entry's lifecycle doesn't use the platform's usual soft-delete
convention (logs are an append-only record, not user-editable content).
"""
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class SystemLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "system_logs"

    level: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="logged")
