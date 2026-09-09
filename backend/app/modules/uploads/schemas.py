"""Pydantic v2 response contracts for the uploads module. No request
schema for the upload itself — FastAPI's UploadFile is used directly in
the router (multipart/form-data, not JSON body)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UploadOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    lesson_id: uuid.UUID | None
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


# --- Sprint 27: presigned (direct-to-R2) upload session flow ---

class CreatePresignedUploadRequest(BaseModel):
    original_filename: str
    content_type: str
    size_bytes: int
    lesson_id: uuid.UUID | None = None


class PresignedUploadOut(BaseModel):
    upload_id: uuid.UUID
    upload_url: str
    required_headers: dict[str, str]


class ViewUrlOut(BaseModel):
    view_url: str


# --- Sprint 27 Amendment: R2 Multipart Upload (2 GB video support) ---

class InitiateMultipartUploadRequest(BaseModel):
    original_filename: str
    content_type: str
    size_bytes: int
    lesson_id: uuid.UUID | None = None


class InitiateMultipartUploadOut(BaseModel):
    upload_id: uuid.UUID
    multipart_upload_id: str
    total_parts: int
    part_size_bytes: int


class PartUrlRequest(BaseModel):
    part_number: int


class PartUrlOut(BaseModel):
    part_number: int
    upload_url: str


class CompletedPart(BaseModel):
    part_number: int
    etag: str


class CompleteMultipartUploadRequest(BaseModel):
    parts: list[CompletedPart]
