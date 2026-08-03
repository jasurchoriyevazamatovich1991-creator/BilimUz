"""
GeneralSetting, SmtpSettings, PaymentSettings, AiSettings ORM models —
mirror `general_settings`, `smtp_settings`, `payment_settings`,
`ai_settings` tables in schema_v2.sql (Module 22). All four have
created_by/updated_by (verified against schema_v2.sql) — AuditMixin used
throughout, unlike attempts/results/analytics.

Secret columns (password, secret_key, api_key) store CIPHERTEXT — the
model layer doesn't know or care that they're encrypted; encryption is a
service-layer concern (EncryptionService), never done in the model.
"""
from enum import StrEnum

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, StatusMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base


class PaymentProvider(StrEnum):
    CLICK = "click"
    PAYME = "payme"
    UZUM_BANK = "uzum_bank"
    HUMO = "humo"
    UZCARD = "uzcard"
    STRIPE = "stripe"


class GeneralSetting(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "general_settings"

    key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)


class SmtpSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "smtp_settings"

    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)  # ciphertext
    from_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PaymentSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "payment_settings"

    provider: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    merchant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    secret_key: Mapped[str | None] = mapped_column(String(255), nullable=True)  # ciphertext


class AiSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin, StatusMixin):
    __tablename__ = "ai_settings"

    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)  # ciphertext
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
