"""
Pydantic v2 request/response contracts for the settings module.

CRITICAL DESIGN RULE: every *Out schema for smtp/payment/ai settings has
NO field for the secret value (password/secret_key/api_key) — not a
nulled-out field, structurally absent from the class. This is checked by
a dedicated test (tests/test_settings_schemas.py) that fails loudly if
anyone ever adds one back.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.settings.constants import MIN_SECRET_LENGTH
from app.modules.settings.validators import validate_port, validate_secret_value


class GeneralSettingUpsertRequest(BaseModel):
    value: dict


class GeneralSettingOut(BaseModel):
    id: uuid.UUID
    key: str
    value: dict
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class SmtpSettingsUpsertRequest(BaseModel):
    host: str
    port: int = 587
    username: str | None = None
    password: str = Field(..., min_length=MIN_SECRET_LENGTH)  # plaintext IN, never OUT
    from_email: str | None = None

    @field_validator("port")
    @classmethod
    def _port(cls, v: int) -> int:
        return validate_port(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return validate_secret_value(v)


class SmtpSettingsOut(BaseModel):
    """No `password` field — see module docstring."""
    id: uuid.UUID
    host: str
    port: int
    username: str | None
    from_email: str | None
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaymentSettingsUpsertRequest(BaseModel):
    provider: str
    merchant_id: str | None = None
    secret_key: str = Field(..., min_length=MIN_SECRET_LENGTH)  # plaintext IN, never OUT

    @field_validator("secret_key")
    @classmethod
    def _secret_key(cls, v: str) -> str:
        return validate_secret_value(v)


class PaymentSettingsOut(BaseModel):
    """No `secret_key` field — see module docstring."""
    id: uuid.UUID
    provider: str
    merchant_id: str | None
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class AiSettingsUpsertRequest(BaseModel):
    provider: str
    api_key: str = Field(..., min_length=MIN_SECRET_LENGTH)  # plaintext IN, never OUT
    model: str | None = None

    @field_validator("api_key")
    @classmethod
    def _api_key(cls, v: str) -> str:
        return validate_secret_value(v)


class AiSettingsOut(BaseModel):
    """No `api_key` field — see module docstring."""
    id: uuid.UUID
    provider: str
    model: str | None
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}
