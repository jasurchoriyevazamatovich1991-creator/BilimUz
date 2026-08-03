"""Data-access layer for NotificationTemplate, Notification,
EmailQueueItem, SmsQueueItem — four repositories in one file, same
cohesive-module reasoning as questions/repository.py."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.notifications.constants import MAX_SEND_ATTEMPTS
from app.modules.notifications.models import EmailQueueItem, Notification, NotificationTemplate, QueueStatus, SmsQueueItem


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, notification_id: uuid.UUID) -> Notification | None:
        stmt = select(Notification).where(Notification.id == notification_id, Notification.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID, page: int, per_page: int, is_read: bool | None) -> tuple[list[Notification], int]:
        stmt = select(Notification).where(Notification.user_id == user_id, Notification.deleted_at.is_(None))
        if is_read is not None:
            stmt = stmt.where(Notification.is_read == is_read)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Notification.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def create(self, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.flush()
        return notification

    def mark_read(self, notification: Notification) -> None:
        notification.is_read = True
        self.db.flush()

    def mark_all_read(self, user_id: uuid.UUID) -> int:
        stmt = select(Notification).where(
            Notification.user_id == user_id, Notification.is_read.is_(False), Notification.deleted_at.is_(None)
        )
        rows = list(self.db.execute(stmt).scalars().all())
        for row in rows:
            row.is_read = True
        self.db.flush()
        return len(rows)

    def commit(self) -> None:
        self.db.commit()


class TemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_code(self, code: str) -> NotificationTemplate | None:
        stmt = select(NotificationTemplate).where(NotificationTemplate.code == code, NotificationTemplate.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active(self) -> list[NotificationTemplate]:
        stmt = select(NotificationTemplate).where(NotificationTemplate.status == "active", NotificationTemplate.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def create(self, template: NotificationTemplate) -> NotificationTemplate:
        self.db.add(template)
        self.db.flush()
        return template

    def commit(self) -> None:
        self.db.commit()


class EmailQueueRepository:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(self, to_email: str, subject: str, body: str) -> EmailQueueItem:
        item = EmailQueueItem(to_email=to_email, subject=subject, body=body)
        self.db.add(item)
        self.db.flush()
        return item

    def list_pending(self, limit: int) -> list[EmailQueueItem]:
        stmt = select(EmailQueueItem).where(EmailQueueItem.status == QueueStatus.PENDING.value).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def mark_sent(self, item: EmailQueueItem) -> None:
        item.status = QueueStatus.SENT.value
        item.sent_at = datetime.now(timezone.utc)
        self.db.flush()

    def mark_attempt_failed(self, item: EmailQueueItem) -> None:
        item.attempts += 1
        if item.attempts >= MAX_SEND_ATTEMPTS:
            item.status = QueueStatus.FAILED.value
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()


class SmsQueueRepository:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(self, to_phone: str, message: str) -> SmsQueueItem:
        item = SmsQueueItem(to_phone=to_phone, message=message)
        self.db.add(item)
        self.db.flush()
        return item

    def list_pending(self, limit: int) -> list[SmsQueueItem]:
        stmt = select(SmsQueueItem).where(SmsQueueItem.status == QueueStatus.PENDING.value).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def mark_sent(self, item: SmsQueueItem) -> None:
        item.status = QueueStatus.SENT.value
        item.sent_at = datetime.now(timezone.utc)
        self.db.flush()

    def mark_attempt_failed(self, item: SmsQueueItem) -> None:
        item.attempts += 1
        if item.attempts >= MAX_SEND_ATTEMPTS:
            item.status = QueueStatus.FAILED.value
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
