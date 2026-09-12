"""Lesson ORM model — mirrors `lessons` table in schema_v2.sql (Module 10).
Belongs to a Topic. Content can be video, PDF, and/or rich text — at
least one is required (enforced in service.py, not at the DB level)."""
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class Lesson(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "lessons"

    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    video: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Sprint 35 — additive. NULL for every lesson that only has the
    # legacy `video` text URL above (unchanged). When set, this is the
    # real, R2-backed, signed-URL-accessible Upload row to prefer.
    video_upload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True,
    )
