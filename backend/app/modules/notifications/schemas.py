"""Pydantic v2 request/response contracts for the notifications module."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.notifications.constants import DEFAULT_QUEUE_BATCH_SIZE, MAX_QUEUE_BATCH_SIZE
from app.modules.notifications.validators import (
    validate_channel,
    validate_email_address,
    validate_phone_for_sms,
    validate_template_code,
    validate_title,
)


class CreateNotificationRequest(BaseModel):
    user_id: uuid.UUID
    title: str
    message: str
    channel: str = "in_app"

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return validate_title(v)

    @field_validator("channel")
    @classmethod
    def _channel(cls, v: str) -> str:
        return validate_channel(v)


class NotificationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    message: str
    channel: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    is_read: bool | None = None


class TemplateCreateRequest(BaseModel):
    code: str
    channel: str
    subject: str | None = None
    body: str

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        return validate_template_code(v)

    @field_validator("channel")
    @classmethod
    def _channel(cls, v: str) -> str:
        return validate_channel(v)


class TemplateOut(BaseModel):
    id: uuid.UUID
    code: str
    channel: str
    subject: str | None
    body: str
    status: str

    model_config = {"from_attributes": True}


class EnqueueEmailRequest(BaseModel):
    to_email: str
    subject: str
    body: str

    @field_validator("to_email")
    @classmethod
    def _to_email(cls, v: str) -> str:
        return validate_email_address(v)


class EnqueueSmsRequest(BaseModel):
    to_phone: str
    message: str = Field(..., max_length=500)

    @field_validator("to_phone")
    @classmethod
    def _to_phone(cls, v: str) -> str:
        return validate_phone_for_sms(v)


class QueueItemOut(BaseModel):
    id: uuid.UUID
    status: str
    attempts: int
    sent_at: datetime | None

    model_config = {"from_attributes": True}


class ProcessQueueRequest(BaseModel):
    batch_size: int = Field(default=DEFAULT_QUEUE_BATCH_SIZE, ge=1, le=MAX_QUEUE_BATCH_SIZE)


class ProcessQueueResponse(BaseModel):
    processed: int
    sent: int
    failed: int
