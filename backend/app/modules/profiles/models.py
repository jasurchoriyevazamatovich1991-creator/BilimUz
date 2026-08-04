"""
Profile ORM model — mirrors `profiles` table in schema_v2.sql (Module 2).
1:1 extension of User, per the approved Variant A architecture decision:
first_name/last_name/birth_date/gender/phone are NOT duplicated here —
they live exclusively on User (single source of truth). This model only
stores fields that genuinely belong to the profile: bio, social links,
address, and the school/learning-center scoping.

Has created_by/updated_by and a generic 'active' status column (verified
against schema_v2.sql) — AuditMixin + StatusMixin both correctly apply.
"""
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class Profile(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram: Mapped[str | None] = mapped_column(String(100), nullable=True)
    instagram: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    school_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True)
    learning_center_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("learning_centers.id"), nullable=True)
