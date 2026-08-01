"""Topic ORM model — mirrors `topics` table in schema_v2.sql (Module 9).
Belongs to a Subject (required) and optionally scoped to a Grade."""
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class Topic(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "topics"

    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("grades.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
