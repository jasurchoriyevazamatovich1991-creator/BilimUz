"""
CertificateTemplate, Certificate, CertificateVerification ORM models —
mirror `certificate_templates`, `certificates`, `certificate_verification`
tables in schema_v2.sql (Module 17).

Only CertificateTemplate has created_by/updated_by (verified against
schema_v2.sql) — Certificate and CertificateVerification do not, so only
the template model uses AuditMixin.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class CertificateTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "certificate_templates"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    design: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Certificate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "certificates"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("results.id"), nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("certificate_templates.id"), nullable=True)
    certificate_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # always NULL in Sprint 7 — see README
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="issued")


class CertificateVerification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "certificate_verification"

    certificate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("certificates.id", ondelete="CASCADE"), nullable=False)
    verification_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    verified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
