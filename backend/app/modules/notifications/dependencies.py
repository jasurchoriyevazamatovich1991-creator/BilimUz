"""
FastAPI dependency wiring for the notifications module.

get_email_provider()/get_sms_provider() return the Unconfigured*
implementations this sprint — the ONLY place that would change when a
real provider is added later (see providers.py module docstring).
"""
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.notifications.providers import (
    EmailProvider,
    SmsProvider,
    UnconfiguredEmailProvider,
    UnconfiguredSmsProvider,
)
from app.modules.notifications.repository import (
    EmailQueueRepository,
    NotificationRepository,
    SmsQueueRepository,
    TemplateRepository,
)
from app.modules.notifications.service import NotificationService, QueueService, TemplateService


@lru_cache
def get_email_provider() -> EmailProvider:
    return UnconfiguredEmailProvider()


@lru_cache
def get_sms_provider() -> SmsProvider:
    return UnconfiguredSmsProvider()


def get_notification_repository(db: Session = Depends(get_db)) -> NotificationRepository:
    return NotificationRepository(db)


def get_notification_service(repo: NotificationRepository = Depends(get_notification_repository)) -> NotificationService:
    return NotificationService(repo)


def get_template_repository(db: Session = Depends(get_db)) -> TemplateRepository:
    return TemplateRepository(db)


def get_template_service(repo: TemplateRepository = Depends(get_template_repository)) -> TemplateService:
    return TemplateService(repo)


def get_email_queue_repository(db: Session = Depends(get_db)) -> EmailQueueRepository:
    return EmailQueueRepository(db)


def get_sms_queue_repository(db: Session = Depends(get_db)) -> SmsQueueRepository:
    return SmsQueueRepository(db)


def get_queue_service(
    email_repo: EmailQueueRepository = Depends(get_email_queue_repository),
    sms_repo: SmsQueueRepository = Depends(get_sms_queue_repository),
    email_provider: EmailProvider = Depends(get_email_provider),
    sms_provider: SmsProvider = Depends(get_sms_provider),
) -> QueueService:
    return QueueService(email_repo, sms_repo, email_provider, sms_provider)
