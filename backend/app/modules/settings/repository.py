"""
Data-access layer for GeneralSetting, SmtpSettings, PaymentSettings,
AiSettings — four repositories in one file, same cohesive-module
reasoning as questions/repository.py.

Each secret-bearing repository has a `get_decrypted_*()` method,
deliberately separate from the normal `get_by_id()`/`list()` methods —
grep-able, obviously-different-looking call sites make it much harder to
accidentally leak a decrypted secret into an HTTP response somewhere.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security.encryption import EncryptionService
from app.modules.settings.models import AiSettings, GeneralSetting, PaymentSettings, SmtpSettings


class GeneralSettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_key(self, key: str) -> GeneralSetting | None:
        stmt = select(GeneralSetting).where(GeneralSetting.key == key, GeneralSetting.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self) -> list[GeneralSetting]:
        stmt = select(GeneralSetting).where(GeneralSetting.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def upsert(self, key: str, value: dict, actor_id: uuid.UUID) -> GeneralSetting:
        existing = self.get_by_key(key)
        if existing:
            existing.value = value
            existing.updated_by = actor_id
            self.db.flush()
            return existing
        row = GeneralSetting(key=key, value=value, created_by=actor_id)
        self.db.add(row)
        self.db.flush()
        return row

    def commit(self) -> None:
        self.db.commit()


class SmtpSettingsRepository:
    """Reused read-only by the `notifications` module — see that
    module's dependencies.py."""

    def __init__(self, db: Session, encryption: EncryptionService):
        self.db = db
        self._encryption = encryption

    def get(self) -> SmtpSettings | None:
        """Single-row config — SMTP has exactly one active configuration,
        unlike payment_settings which has one per provider."""
        stmt = select(SmtpSettings).where(SmtpSettings.deleted_at.is_(None)).order_by(SmtpSettings.updated_at.desc())
        return self.db.execute(stmt).scalars().first()

    def get_decrypted_password(self) -> str | None:
        row = self.get()
        if row is None or row.password is None:
            return None
        return self._encryption.decrypt(row.password)

    def upsert(self, host: str, port: int, username: str | None, plaintext_password: str, from_email: str | None, actor_id: uuid.UUID) -> SmtpSettings:
        encrypted = self._encryption.encrypt(plaintext_password)
        existing = self.get()
        if existing:
            existing.host, existing.port, existing.username = host, port, username
            existing.password, existing.from_email, existing.updated_by = encrypted, from_email, actor_id
            self.db.flush()
            return existing
        row = SmtpSettings(host=host, port=port, username=username, password=encrypted, from_email=from_email, created_by=actor_id)
        self.db.add(row)
        self.db.flush()
        return row

    def commit(self) -> None:
        self.db.commit()


class PaymentSettingsRepository:
    def __init__(self, db: Session, encryption: EncryptionService):
        self.db = db
        self._encryption = encryption

    def get_by_provider(self, provider: str) -> PaymentSettings | None:
        stmt = select(PaymentSettings).where(PaymentSettings.provider == provider, PaymentSettings.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_decrypted_secret(self, provider: str) -> str | None:
        row = self.get_by_provider(provider)
        if row is None or row.secret_key is None:
            return None
        return self._encryption.decrypt(row.secret_key)

    def upsert(self, provider: str, merchant_id: str | None, plaintext_secret: str, actor_id: uuid.UUID) -> PaymentSettings:
        encrypted = self._encryption.encrypt(plaintext_secret)
        existing = self.get_by_provider(provider)
        if existing:
            existing.merchant_id, existing.secret_key, existing.updated_by = merchant_id, encrypted, actor_id
            self.db.flush()
            return existing
        row = PaymentSettings(provider=provider, merchant_id=merchant_id, secret_key=encrypted, created_by=actor_id)
        self.db.add(row)
        self.db.flush()
        return row

    def commit(self) -> None:
        self.db.commit()


class AiSettingsRepository:
    def __init__(self, db: Session, encryption: EncryptionService):
        self.db = db
        self._encryption = encryption

    def get(self) -> AiSettings | None:
        stmt = select(AiSettings).where(AiSettings.deleted_at.is_(None)).order_by(AiSettings.updated_at.desc())
        return self.db.execute(stmt).scalars().first()

    def get_decrypted_api_key(self) -> str | None:
        row = self.get()
        if row is None or row.api_key is None:
            return None
        return self._encryption.decrypt(row.api_key)

    def upsert(self, provider: str, plaintext_api_key: str, model: str | None, actor_id: uuid.UUID) -> AiSettings:
        encrypted = self._encryption.encrypt(plaintext_api_key)
        existing = self.get()
        if existing:
            existing.provider, existing.api_key, existing.model, existing.updated_by = provider, encrypted, model, actor_id
            self.db.flush()
            return existing
        row = AiSettings(provider=provider, api_key=encrypted, model=model, created_by=actor_id)
        self.db.add(row)
        self.db.flush()
        return row

    def commit(self) -> None:
        self.db.commit()
