"""
AiChat, AiHistoryEntry, AiRecommendation, StudyPlan ORM models — mirror
`ai_chats`, `ai_history`, `ai_recommendations`, `study_plans` tables in
schema_v2.sql (Module 21).

None of the four tables have created_by/updated_by (verified against
schema_v2.sql) — no AuditMixin. All four have a generic 'active' status
column (not a domain-specific enum like notifications' queue_status), so
StatusMixin is used throughout, correctly this time.
"""
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class AiChat(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "ai_chats"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AiHistoryEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "ai_history"

    chat_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_chats.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)


class AiRecommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "ai_recommendations"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class StudyPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "study_plans"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    plan: Mapped[dict] = mapped_column(JSONB, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
