"""
LessonProgress ORM model — mirrors `lesson_progress` table (migration
0009). New module, Sprint 36 — Student Progress / Lesson Completion.

No StatusMixin/AuditMixin: a progress record has no "active/inactive"
lifecycle (unlike Notification) and no "who created/updated it on
behalf of someone else" concept (it's always the student's own action)
— both mixins would add meaningless columns here.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class LessonProgress(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress_user_lesson"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
