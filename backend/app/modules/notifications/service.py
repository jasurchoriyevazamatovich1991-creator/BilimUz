"""
Business logic for notifications: in-app CRUD, templates, and the
queue/trigger delivery engine.

No dependency on the `settings` module is wired in THIS sprint — the
Unconfigured providers (providers.py) don't need SMTP credentials to
honestly refuse to send. A future real provider implementation would
read `SmtpSettingsRepository.get_decrypted_password()` (settings module,
read-only) from within its OWN constructor, not from this service —
keeping that future change isolated to providers.py, never touching
NotificationService/QueueService.
"""
import uuid

from app.core.audit import log_action
from app.modules.notifications.exceptions import (
    NotificationNotFoundException,
    ProviderNotConfiguredException,
    TemplateCodeAlreadyExistsException,
)
from app.modules.notifications.models import EmailQueueItem, Notification, NotificationTemplate, SmsQueueItem
from app.modules.notifications.providers import EmailProvider, SmsProvider
from app.modules.notifications.repository import (
    EmailQueueRepository,
    NotificationRepository,
    SmsQueueRepository,
    TemplateRepository,
)
from app.modules.notifications.schemas import ProcessQueueResponse


class NotificationService:
    def __init__(self, repository: NotificationRepository):
        self.repo = repository

    def create(self, user_id: uuid.UUID, title: str, message: str, channel: str, actor_id: uuid.UUID) -> Notification:
        notification = Notification(user_id=user_id, title=title, message=message, channel=channel)
        self.repo.create(notification)
        log_action(self.repo.db, action="notification.created", user_id=actor_id, entity_type="notification", entity_id=notification.id)
        self.repo.commit()
        return notification

    def list_mine(self, user_id: uuid.UUID, page: int, per_page: int, is_read: bool | None) -> tuple[list[Notification], int]:
        return self.repo.list_for_user(user_id, page, per_page, is_read)

    def mark_read(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification:
        notification = self.repo.get_by_id(notification_id)
        if notification is None or notification.user_id != user_id:
            raise NotificationNotFoundException("Bildirishnoma topilmadi")
        self.repo.mark_read(notification)
        self.repo.commit()
        return notification

    def mark_all_read(self, user_id: uuid.UUID) -> int:
        count = self.repo.mark_all_read(user_id)
        self.repo.commit()
        return count


class TemplateService:
    def __init__(self, repository: TemplateRepository):
        self.repo = repository

    def create(self, code: str, channel: str, subject: str | None, body: str, actor_id: uuid.UUID) -> NotificationTemplate:
        if self.repo.get_by_code(code):
            raise TemplateCodeAlreadyExistsException("Bu kod bilan shablon allaqachon mavjud")
        template = NotificationTemplate(code=code, channel=channel, subject=subject, body=body, created_by=actor_id)
        self.repo.create(template)
        self.repo.commit()
        return template

    def list_active(self) -> list[NotificationTemplate]:
        return self.repo.list_active()


class QueueService:
    """The delivery engine — queue + trigger only, per the approved
    scope. `email_provider`/`sms_provider` are the honest
    Unconfigured* implementations this sprint (see providers.py)."""

    def __init__(
        self,
        email_repository: EmailQueueRepository,
        sms_repository: SmsQueueRepository,
        email_provider: EmailProvider,
        sms_provider: SmsProvider,
    ):
        self.email_repo = email_repository
        self.sms_repo = sms_repository
        self.email_provider = email_provider
        self.sms_provider = sms_provider

    def enqueue_email(self, to_email: str, subject: str, body: str) -> EmailQueueItem:
        item = self.email_repo.enqueue(to_email, subject, body)
        self.email_repo.commit()
        return item

    def enqueue_sms(self, to_phone: str, message: str) -> SmsQueueItem:
        item = self.sms_repo.enqueue(to_phone, message)
        self.sms_repo.commit()
        return item

    def process_email_queue(self, batch_size: int) -> ProcessQueueResponse:
        pending = self.email_repo.list_pending(batch_size)
        sent = self._process_batch(pending, self.email_provider, self.email_repo, is_email=True)
        self.email_repo.commit()
        return ProcessQueueResponse(processed=len(pending), sent=sent, failed=len(pending) - sent)

    def process_sms_queue(self, batch_size: int) -> ProcessQueueResponse:
        pending = self.sms_repo.list_pending(batch_size)
        sent = self._process_batch(pending, self.sms_provider, self.sms_repo, is_email=False)
        self.sms_repo.commit()
        return ProcessQueueResponse(processed=len(pending), sent=sent, failed=len(pending) - sent)

    def _process_batch(self, items, provider, repo, is_email: bool) -> int:
        """Fails fast on ProviderNotConfiguredException (a systemic
        condition, not a per-message one) — propagates immediately
        rather than looping through every pending row uselessly or
        faking a partial-success response."""
        sent_count = 0
        for item in items:
            try:
                if is_email:
                    provider.send(item.to_email, item.subject, item.body)
                else:
                    provider.send(item.to_phone, item.message)
                repo.mark_sent(item)
                sent_count += 1
            except ProviderNotConfiguredException:
                raise
            except Exception:
                repo.mark_attempt_failed(item)
        return sent_count
