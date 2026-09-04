"""Pydantic v2 request/response contracts for the certificates module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.certificates.validators import validate_template_name


class IssueCertificateRequest(BaseModel):
    result_id: uuid.UUID
    template_id: uuid.UUID | None = None


class CertificateOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    result_id: uuid.UUID
    template_id: uuid.UUID | None
    certificate_number: str
    pdf_url: str | None  # always null in Sprint 7 — see README
    status: str
    created_at: datetime
    # Not a column on the `certificates` table — lives on the separate
    # CertificateVerification record (certificate_verification table).
    # The service layer attaches it as a transient attribute on the
    # Certificate ORM instance before validation (see service.py's
    # `_with_verification_code`), so this reads correctly via
    # `from_attributes=True` without any model/migration change. Safe
    # to expose to the certificate's own owner — it's the public,
    # non-secret token the whole verification feature exists to share
    # (see GET /certificates/verify/{code}'s own docstring).
    verification_code: str

    model_config = {"from_attributes": True}


class CertificateListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


class TemplateCreateRequest(BaseModel):
    name: str
    design: dict | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return validate_template_name(v)


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    design: dict | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VerificationResultOut(BaseModel):
    """Public — deliberately minimal, no user PII beyond what's needed
    to confirm the certificate is genuine."""
    certificate_number: str
    is_valid: bool
    verified_count: int
