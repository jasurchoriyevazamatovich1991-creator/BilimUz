"""
Pydantic v2 response contracts for the audit_logs module. Read-only —
no request/create schema, since this module never writes to audit_logs
(that's core.audit.log_action()'s job, unchanged).
"""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class AuditLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    ip_address: str | None
    # AuditLog's Python attribute is `metadata_` (SQLAlchemy reserves
    # `metadata` on the declarative base) — read from that attribute,
    # serialize as `metadata` in the JSON response.
    metadata: dict | None = Field(default=None, validation_alias="metadata_", serialization_alias="metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class AuditLogListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    user_id: uuid.UUID | None = None
    action: str | None = None
    entity_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
