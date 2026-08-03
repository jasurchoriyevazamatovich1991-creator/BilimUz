"""
NotificationTemplate, Notification, EmailQueueItem, SmsQueueItem ORM
models — mirror `notification_templates`, `notifications`,
`email_queue`, `sms_queue` tables in schema_v2.sql (Module 19).

Only NotificationTemplate has created_by/updated_by (verified against
schema_v2.sql) — AuditMixin used selectively, same pattern as
certificates. `StatusMixin` is used only for NotificationTemplate and
Notification (generic 'active' lifecycle status, per its own docstring:
"Tables that already define their own status should NOT use this
mixin") — EmailQueueItem/SmsQueueItem have a DOMAIN-SPECIFIC status
(pending/sent/failed, the schema's `queue_status` enum), so they define
`status` directly instead, correctly following that same documented rule.
"""
import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class QueueStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "notification_templates"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin, StatusMixin):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="in_app")
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class EmailQueueItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """No StatusMixin — `status` here is the domain-specific queue state
    (pending/sent/failed), not the generic active/inactive lifecycle."""
    __tablename__ = "email_queue"

    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=QueueStatus.PENDING)


class SmsQueueItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """No StatusMixin — same reasoning as EmailQueueItem."""
    __tablename__ = "sms_queue"

    to_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=QueueStatus.PENDING)
