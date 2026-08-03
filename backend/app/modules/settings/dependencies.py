"""FastAPI dependency wiring for the settings module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.security.dependencies import get_encryption_service
from app.core.security.encryption import EncryptionService
from app.db.session import get_db
from app.modules.settings.repository import (
    AiSettingsRepository,
    GeneralSettingsRepository,
    PaymentSettingsRepository,
    SmtpSettingsRepository,
)
from app.modules.settings.service import (
    AiSettingsService,
    GeneralSettingsService,
    PaymentSettingsService,
    SmtpSettingsService,
)


def get_general_settings_repository(db: Session = Depends(get_db)) -> GeneralSettingsRepository:
    return GeneralSettingsRepository(db)


def get_general_settings_service(repo: GeneralSettingsRepository = Depends(get_general_settings_repository)) -> GeneralSettingsService:
    return GeneralSettingsService(repo)


def get_smtp_settings_repository(
    db: Session = Depends(get_db), encryption: EncryptionService = Depends(get_encryption_service)
) -> SmtpSettingsRepository:
    return SmtpSettingsRepository(db, encryption)


def get_smtp_settings_service(repo: SmtpSettingsRepository = Depends(get_smtp_settings_repository)) -> SmtpSettingsService:
    return SmtpSettingsService(repo)


def get_payment_settings_repository(
    db: Session = Depends(get_db), encryption: EncryptionService = Depends(get_encryption_service)
) -> PaymentSettingsRepository:
    return PaymentSettingsRepository(db, encryption)


def get_payment_settings_service(repo: PaymentSettingsRepository = Depends(get_payment_settings_repository)) -> PaymentSettingsService:
    return PaymentSettingsService(repo)


def get_ai_settings_repository(
    db: Session = Depends(get_db), encryption: EncryptionService = Depends(get_encryption_service)
) -> AiSettingsRepository:
    return AiSettingsRepository(db, encryption)


def get_ai_settings_service(repo: AiSettingsRepository = Depends(get_ai_settings_repository)) -> AiSettingsService:
    return AiSettingsService(repo)
