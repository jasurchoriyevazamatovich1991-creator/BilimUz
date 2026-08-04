"""School ORM model — mirrors `schools` table in schema_v2.sql (Module 5).
Standalone lookup entity this sprint — `profiles.school_id` references
this table, but `profiles` itself is not yet built (see architecture
doc's "Critical finding"). Has created_by/updated_by and a generic
'active' status column (verified against schema_v2.sql) — AuditMixin +
StatusMixin both correctly apply here."""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class School(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "schools"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
