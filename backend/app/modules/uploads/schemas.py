"""Pydantic v2 response contracts for the uploads module. No request
schema for the upload itself — FastAPI's UploadFile is used directly in
the router (multipart/form-data, not JSON body)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UploadOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    file_name: str
    file_type: str
    size_bytes: int | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ImageOut(BaseModel):
    id: uuid.UUID
    upload_id: uuid.UUID
    width: int | None
    height: int | None
    alt_text: str | None

    model_config = {"from_attributes": True}


class VideoOut(BaseModel):
    id: uuid.UUID
    upload_id: uuid.UUID
    duration_seconds: int | None  # always null this sprint — see README
    thumbnail_url: str | None

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: uuid.UUID
    upload_id: uuid.UUID
    page_count: int | None  # always null this sprint — see README

    model_config = {"from_attributes": True}


class UploadListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
