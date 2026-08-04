"""LearningCenter ORM model — mirrors `learning_centers` table in
schema_v2.sql (Module 6). Standalone lookup entity this sprint —
structurally near-identical to `School` but kept as a separate module
per the schema's own module boundary. Has created_by/updated_by and a
generic 'active' status column (verified against schema_v2.sql) —
AuditMixin + StatusMixin both correctly apply here."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class LearningCenter(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "learning_centers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
