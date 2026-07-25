"""
Central audit logging. Binds to the `audit_logs` table (schema_v2.sql,
Module 24) — lives in core, not a feature module, because every module
needs to write to it and it must not create a circular dependency
(auth -> audit -> auth). Never call this with a password or token value.
"""
import uuid
from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base
from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="logged")


def log_action(
    db: Session,
    action: str,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Fire-and-forget within the current transaction — caller still
    commits. Never pass password_hash, tokens, or verification codes in
    `metadata`."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            metadata_=metadata,
        )
    )
    db.flush()
