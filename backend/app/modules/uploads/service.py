"""
Business logic for file uploads. Validates type/size before anything
touches disk, generates a UUID-based storage name (never trusts the
caller's filename for the actual path), routes to the correct metadata
table. Talks to disk only through StorageBackend — never open()/os.*
directly.
"""
import uuid
from typing import BinaryIO

from app.core.audit import log_action
from app.modules.uploads.constants import FILE_TYPE_DOCUMENT, FILE_TYPE_IMAGE, FILE_TYPE_VIDEO
from app.modules.uploads.exceptions import FileTooLargeException, UnsupportedFileTypeException, UploadNotFoundException
from app.modules.uploads.models import Document, Image, Upload, Video
from app.modules.uploads.repository import DocumentRepository, ImageRepository, UploadRepository, VideoRepository
from app.modules.uploads.storage import StorageBackend
from app.modules.uploads.validators import classify_content_type, extension_for_content_type, sanitize_display_filename


class UploadService:
    def __init__(
        self,
        repository: UploadRepository,
        image_repository: ImageRepository,
        video_repository: VideoRepository,
        document_repository: DocumentRepository,
        storage: StorageBackend,
    ):
        self.repo = repository
        self.image_repo = image_repository
        self.video_repo = video_repository
        self.document_repo = document_repository
        self.storage = storage

    def upload(self, stream: BinaryIO, original_filename: str, content_type: str, size_bytes: int, user_id: uuid.UUID) -> Upload:
        classification = classify_content_type(content_type)
        if classification is None:
            raise UnsupportedFileTypeException(f"Fayl turi qo'llab-quvvatlanmaydi: {content_type}")
        file_type, max_size = classification
        if size_bytes > max_size:
            raise FileTooLargeException(f"Fayl juda katta — maksimal {max_size // (1024*1024)} MB")

        generated_name = f"{uuid.uuid4()}{extension_for_content_type(content_type)}"
        file_url = self.storage.save(generated_name, stream)

        upload = Upload(
            user_id=user_id, file_name=sanitize_display_filename(original_filename),
            file_url=file_url, file_type=file_type, size_bytes=size_bytes,
        )
        self.repo.create(upload)
        self._create_type_metadata(upload, file_type)
        log_action(self.repo.db, action="upload.created", user_id=user_id, entity_type="upload", entity_id=upload.id)
        self.repo.commit()
        return upload

    def get(self, upload_id: uuid.UUID, user_id: uuid.UUID) -> Upload:
        upload = self.repo.get_by_id(upload_id)
        if upload is None or upload.user_id != user_id:
            raise UploadNotFoundException("Fayl topilmadi")
        return upload

    def list_mine(self, user_id: uuid.UUID, page: int, per_page: int) -> tuple[list[Upload], int]:
        return self.repo.list_for_user(user_id, page, per_page)

    def delete(self, upload_id: uuid.UUID, user_id: uuid.UUID) -> None:
        upload = self.get(upload_id, user_id)
        self.storage.delete(upload.file_url)  # physical file removed — deliberate exception, see README
        self.repo.soft_delete(upload)
        log_action(self.repo.db, action="upload.deleted", user_id=user_id, entity_type="upload", entity_id=upload_id)
        self.repo.commit()

    def open_for_download(self, upload_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Upload, BinaryIO]:
        upload = self.get(upload_id, user_id)
        return upload, self.storage.read(upload.file_url)

    def _create_type_metadata(self, upload: Upload, file_type: str) -> None:
        """Width/height, duration, and page_count are all NULL this
        sprint (approved scope boundary — no extraction library chosen
        yet, see README) — the row is still created for FK integrity and
        future backfill, it's just missing the derived fields for now."""
        if file_type == FILE_TYPE_IMAGE:
            self.image_repo.create(Image(upload_id=upload.id, width=None, height=None))
        elif file_type == FILE_TYPE_VIDEO:
            self.video_repo.create(Video(upload_id=upload.id, duration_seconds=None))
        elif file_type == FILE_TYPE_DOCUMENT:
            self.document_repo.create(Document(upload_id=upload.id, page_count=None))
        # FILE_TYPE_AUDIO has no dedicated metadata table in the schema —
        # tracked in `uploads` only, by design (see architecture doc).
