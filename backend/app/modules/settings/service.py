"""
Business logic for platform settings. Secret values are encrypted before
every write (inside the repository, using EncryptionService) and never
returned by any service method a router would serialize into a response
— only *Out schemas without the secret field ever leave this module via
HTTP.
"""
import uuid

from app.core.audit import log_action
from app.modules.settings.exceptions import SettingNotFoundException
from app.modules.settings.models import AiSettings, GeneralSetting, PaymentSettings, SmtpSettings
from app.modules.settings.repository import (
    AiSettingsRepository,
    GeneralSettingsRepository,
    PaymentSettingsRepository,
    SmtpSettingsRepository,
)
from app.modules.settings.validators import validate_setting_key


class GeneralSettingsService:
    def __init__(self, repository: GeneralSettingsRepository):
        self.repo = repository

    def get(self, key: str) -> GeneralSetting:
        setting = self.repo.get_by_key(validate_setting_key(key))
        if setting is None:
            raise SettingNotFoundException("Sozlama topilmadi")
        return setting

    def list_all(self) -> list[GeneralSetting]:
        return self.repo.list_all()

    def upsert(self, key: str, value: dict, actor_id: uuid.UUID) -> GeneralSetting:
        setting = self.repo.upsert(validate_setting_key(key), value, actor_id)
        log_action(self.repo.db, action="settings.general_updated", user_id=actor_id, metadata={"key": key})
        self.repo.commit()
        return setting


class SmtpSettingsService:
    def __init__(self, repository: SmtpSettingsRepository):
        self.repo = repository

    def get(self) -> SmtpSettings | None:
        return self.repo.get()

    def upsert(self, host: str, port: int, username: str | None, password: str, from_email: str | None, actor_id: uuid.UUID) -> SmtpSettings:
        row = self.repo.upsert(host, port, username, password, from_email, actor_id)
        log_action(self.repo.db, action="settings.smtp_updated", user_id=actor_id)  # never logs the password
        self.repo.commit()
        return row


class PaymentSettingsService:
    def __init__(self, repository: PaymentSettingsRepository):
        self.repo = repository

    def upsert(self, provider: str, merchant_id: str | None, secret_key: str, actor_id: uuid.UUID) -> PaymentSettings:
        row = self.repo.upsert(provider, merchant_id, secret_key, actor_id)
        log_action(self.repo.db, action="settings.payment_updated", user_id=actor_id, metadata={"provider": provider})
        self.repo.commit()
        return row

    def get(self, provider: str) -> PaymentSettings:
        row = self.repo.get_by_provider(provider)
        if row is None:
            raise SettingNotFoundException("To'lov sozlamasi topilmadi")
        return row


class AiSettingsService:
    def __init__(self, repository: AiSettingsRepository):
        self.repo = repository

    def get(self) -> AiSettings | None:
        return self.repo.get()

    def upsert(self, provider: str, api_key: str, model: str | None, actor_id: uuid.UUID) -> AiSettings:
        row = self.repo.upsert(provider, api_key, model, actor_id)
        log_action(self.repo.db, action="settings.ai_updated", user_id=actor_id)  # never logs the api_key
        self.repo.commit()
        return row
