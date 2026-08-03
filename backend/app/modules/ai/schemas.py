"""Pydantic v2 request/response contracts for the ai module."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.ai.validators import validate_message_content


class SendMessageRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _content(cls, v: str) -> str:
        return validate_message_content(v)


class ChatOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryEntryOut(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    role: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatDetailOut(ChatOut):
    history: list[HistoryEntryOut] = []


class MessageResponseOut(BaseModel):
    """The assistant's reply, plus the chat it belongs to — returned by
    POST /chats/{id}/messages."""
    chat_id: uuid.UUID
    user_message: HistoryEntryOut
    assistant_message: HistoryEntryOut


class RecommendationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    subject_id: uuid.UUID | None
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StudyPlanCreateRequest(BaseModel):
    subject_id: uuid.UUID | None = None
    plan: dict
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _validate_dates(self) -> "StudyPlanCreateRequest":
        if self.start_date > self.end_date:
            raise ValueError("Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas")
        return self


class StudyPlanOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    subject_id: uuid.UUID | None
    plan: dict
    start_date: date
    end_date: date
    status: str

    model_config = {"from_attributes": True}


class ChatListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
