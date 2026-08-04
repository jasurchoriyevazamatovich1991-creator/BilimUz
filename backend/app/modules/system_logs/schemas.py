"""Pydantic v2 request/response contracts for the system_logs module."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.system_logs.validators import validate_level, validate_message, validate_source


class CreateSystemLogRequest(BaseModel):
    level: str
    source: str | None = None
    message: str
    context: dict | None = None

    @field_validator("level")
    @classmethod
    def _level(cls, v: str) -> str:
        return validate_level(v)

    @field_validator("message")
    @classmethod
    def _message(cls, v: str) -> str:
        return validate_message(v)

    @field_validator("source")
    @classmethod
    def _source(cls, v: str | None) -> str | None:
        return validate_source(v)


class SystemLogOut(BaseModel):
    id: uuid.UUID
    level: str
    source: str | None
    message: str
    context: dict | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SystemLogListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    level: str | None = None
    source: str | None = None
    date_from: date | None = None
    date_to: date | None = None
