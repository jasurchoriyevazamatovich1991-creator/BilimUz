"""
Upload, Image, Video, Document ORM models — mirror `uploads`, `images`,
`videos`, `documents` tables in schema_v2.sql (Module 23).

None of the four tables have created_by/updated_by (verified against
schema_v2.sql) — no AuditMixin.

video.duration_seconds and document.page_count stay NULL by design this
sprint (approved scope boundary — no metadata extraction, not a
placeholder) — see README.
"""
import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class Upload(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "uploads"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(30), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class Image(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "images"

    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Video(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "videos"

    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)  # always NULL this sprint — see README
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "documents"

    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # always NULL this sprint — see README
