"""
Business logic for file uploads. Validates type/size before anything
touches disk, generates a UUID-based storage name (never trusts the
caller's filename for the actual path), routes to the correct metadata
table. Talks to disk only through StorageBackend — never open()/os.*
directly.

Sprint 27: added the presigned (direct-to-R2) upload session flow.
LessonRepository is a new, READ-ONLY cross-module dependency (same
one-directional shape as Topics reading Subjects/Grades read-only) —
used only to verify a lesson_id exists, never to write to Lessons.
"""
import math
import uuid
from typing import BinaryIO

from app.core.audit import log_action
from app.modules.lessons.repository import LessonRepository
from app.modules.uploads.constants import (
    FILE_TYPE_DOCUMENT,
    FILE_TYPE_IMAGE,
    FILE_TYPE_VIDEO,
    LEGACY_UPLOAD_MAX_VIDEO_SIZE,
    MULTIPART_MAX_PART_NUMBER,
    MULTIPART_PART_SIZE_BYTES,
    PRESIGNED_DOWNLOAD_TTL_SECONDS,
    PRESIGNED_UPLOAD_TTL_SECONDS,
    UPLOAD_STATUS_FAILED,
    UPLOAD_STATUS_PENDING,
    UPLOAD_STATUS_READY,
)
from app.modules.uploads.exceptions import (
    FileTooLargeException,
    InvalidPartNumberException,
    LessonNotFoundException,
    LessonUploadNotPermittedException,
    MissingPartsException,
    NotAMultipartUploadException,
    UnsupportedFileTypeException,
    UploadNotFoundException,
    UploadNotReadyException,
)
from app.modules.uploads.models import Document, Image, Upload, Video
from app.modules.uploads.repository import DocumentRepository, ImageRepository, UploadRepository, VideoRepository
from app.modules.uploads.storage import PresignedUpload, StorageBackend
from app.modules.uploads.validators import build_object_key, classify_content_type, extension_for_content_type, sanitize_display_filename

# Matches lessons/router.py's own require_roles("Admin", "Super Admin",
# "Teacher") on write endpoints exactly — not a new, invented tier.
LESSON_UPLOAD_ALLOWED_ROLES = {"Admin", "Super Admin", "Teacher"}


class UploadService:
    def __init__(
        self,
        repository: UploadRepository,
        image_repository: ImageRepository,
        video_repository: VideoRepository,
        document_repository: DocumentRepository,
        storage: StorageBackend,
        lesson_repository: LessonRepository,
    ):
        self.repo = repository
        self.image_repo = image_repository
        self.video_repo = video_repository
        self.document_repo = document_repository
        self.storage = storage
        self.lesson_repo = lesson_repository

    def _verify_bounded_stream_size(self, stream: BinaryIO, max_size: int) -> None:
        """Sprint 29 fix. Reads `stream` in small, fixed-size chunks and
        raises the moment the cumulative size would exceed `max_size` —
        never materializes more than one chunk (1 MB) in memory at
        once, unlike a bare `stream.read()`. This is a genuine defense
        against a client that lies about the declared Content-
        Length/size (the fast-path declared-size check in upload()
        below is skipped or spoofed) — the real byte count is what's
        enforced here, not just what the client claims.

        Resets the stream position to the start afterward so the
        unmodified, existing `storage.save()` call downstream can read
        the (now proven-bounded) content again from the beginning —
        StorageBackend/LocalDiskStorage/R2Storage are not touched by
        this fix at all.
        """
        CHUNK_SIZE = 1024 * 1024  # 1 MB — bounded, regardless of the file's real or declared size
        total_read = 0
        while True:
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > max_size:
                raise FileTooLargeException(f"Fayl juda katta — maksimal {max_size // (1024*1024)} MB")
        stream.seek(0)

    def upload(self, stream: BinaryIO, original_filename: str, content_type: str, size_bytes: int, user_id: uuid.UUID) -> Upload:
        classification = classify_content_type(content_type)
        if classification is None:
            raise UnsupportedFileTypeException(f"Fayl turi qo'llab-quvvatlanmaydi: {content_type}")
        file_type, max_size = classification

        if file_type == FILE_TYPE_VIDEO:
            # Sprint 29 fix — the legacy, backend-mediated endpoint uses
            # a small dedicated limit for video, NOT the R2/multipart
            # 2 GB ceiling (`max_size` from classify_content_type above
            # is still MAX_SIZE_VIDEO — only ever used here as the
            # general video-type check, immediately overridden below
            # for this legacy path specifically). Every other file type
            # (image/PDF/audio) keeps its existing, already-small limit
            # and existing declared-size-only check, completely
            # unchanged — they were never the actual risk.
            if size_bytes > LEGACY_UPLOAD_MAX_VIDEO_SIZE:
                raise FileTooLargeException(f"Fayl juda katta — maksimal {LEGACY_UPLOAD_MAX_VIDEO_SIZE // (1024*1024)} MB")
            self._verify_bounded_stream_size(stream, LEGACY_UPLOAD_MAX_VIDEO_SIZE)
        elif size_bytes > max_size:
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

    # --- Sprint 27: presigned (direct-to-R2) upload session flow ---

    def create_presigned_session(
        self,
        original_filename: str,
        content_type: str,
        size_bytes: int,
        user_id: uuid.UUID,
        user_role: str,
        lesson_id: uuid.UUID | None,
    ) -> tuple[Upload, PresignedUpload]:
        """Creates a status=pending Upload row and returns a short-lived
        presigned PUT URL for the browser to upload directly to R2 — the
        file's bytes never transit this backend. Validation (type/size,
        lesson existence, lesson-write RBAC) all happens BEFORE any
        presigned URL is generated, matching the existing synchronous
        upload() method's "validate before anything touches storage"
        ordering."""
        classification = classify_content_type(content_type)
        if classification is None:
            raise UnsupportedFileTypeException(f"Fayl turi qo'llab-quvvatlanmaydi: {content_type}")
        file_type, max_size = classification
        if size_bytes > max_size:
            raise FileTooLargeException(f"Fayl juda katta — maksimal {max_size // (1024*1024)} MB")

        if lesson_id is not None:
            if self.lesson_repo.get_by_id(lesson_id) is None:
                raise LessonNotFoundException("Dars topilmadi")
            if user_role not in LESSON_UPLOAD_ALLOWED_ROLES:
                raise LessonUploadNotPermittedException("Ushbu darsga fayl biriktirish uchun ruxsatingiz yo'q")

        object_key = build_object_key(file_type, lesson_id, content_type)
        upload = Upload(
            user_id=user_id, lesson_id=lesson_id,
            file_name=sanitize_display_filename(original_filename),
            file_url=object_key, file_type=file_type, size_bytes=size_bytes,
            status=UPLOAD_STATUS_PENDING,
        )
        self.repo.create(upload)
        self._create_type_metadata(upload, file_type)
        log_action(self.repo.db, action="upload.session_created", user_id=user_id, entity_type="upload", entity_id=upload.id)
        self.repo.commit()

        presigned = self.storage.create_presigned_upload(object_key, content_type, PRESIGNED_UPLOAD_TTL_SECONDS)
        return upload, presigned

    def finalize_upload(self, upload_id: uuid.UUID, user_id: uuid.UUID) -> Upload:
        """Called by the browser after the direct R2 PUT succeeds —
        flips pending -> ready. Ownership-checked the same way every
        other module checks it (404, not 403, for a non-owned upload —
        matches Attempts/Certificates/Notifications exactly)."""
        upload = self.get(upload_id, user_id)
        upload.status = UPLOAD_STATUS_READY
        self.repo.commit()
        log_action(self.repo.db, action="upload.finalized", user_id=user_id, entity_type="upload", entity_id=upload.id)
        return upload

    def get_view_url(self, upload_id: uuid.UUID, user_id: uuid.UUID) -> str:
        """Authorization branches on whether this upload is lesson-linked:
        lesson-linked media is authorized the same way the underlying
        Lesson itself is (GET /lessons/{id} is public, verified in
        Sprint 27's audit) — any authenticated user may view it, not
        just the uploader. A PERSONAL (non-lesson) upload keeps the
        existing strict ownership check unchanged. Either way, a
        made-up/non-existent upload_id gets 404, never leaking whether
        the ID exists (same anti-enumeration shape used everywhere else)."""
        upload = self.repo.get_by_id(upload_id)
        if upload is None:
            raise UploadNotFoundException("Fayl topilmadi")
        if upload.lesson_id is None and upload.user_id != user_id:
            raise UploadNotFoundException("Fayl topilmadi")
        if upload.status != UPLOAD_STATUS_READY:
            raise UploadNotReadyException("Fayl hali tayyor emas")
        return self.storage.create_presigned_download(upload.file_url, PRESIGNED_DOWNLOAD_TTL_SECONDS)

    # --- Sprint 27 Amendment: R2 Multipart Upload (2 GB video support) ---

    def initiate_multipart_upload(
        self,
        original_filename: str,
        content_type: str,
        size_bytes: int,
        user_id: uuid.UUID,
        user_role: str,
        lesson_id: uuid.UUID | None,
    ) -> tuple[Upload, str, int]:
        """Same validation ordering as create_presigned_session (type,
        size, lesson existence, lesson-write RBAC all checked BEFORE
        anything is created on R2 or in the database) — this is
        genuinely the large-file sibling of that method, not a
        different code path with different rules."""
        classification = classify_content_type(content_type)
        if classification is None:
            raise UnsupportedFileTypeException(f"Fayl turi qo'llab-quvvatlanmaydi: {content_type}")
        file_type, max_size = classification
        if size_bytes > max_size:
            raise FileTooLargeException(f"Fayl juda katta — maksimal {max_size // (1024*1024)} MB")

        if lesson_id is not None:
            if self.lesson_repo.get_by_id(lesson_id) is None:
                raise LessonNotFoundException("Dars topilmadi")
            if user_role not in LESSON_UPLOAD_ALLOWED_ROLES:
                raise LessonUploadNotPermittedException("Ushbu darsga fayl biriktirish uchun ruxsatingiz yo'q")

        object_key = build_object_key(file_type, lesson_id, content_type)
        multipart_upload_id = self.storage.create_multipart_upload(object_key, content_type)

        upload = Upload(
            user_id=user_id, lesson_id=lesson_id,
            file_name=sanitize_display_filename(original_filename),
            file_url=object_key, file_type=file_type, size_bytes=size_bytes,
            status=UPLOAD_STATUS_PENDING, multipart_upload_id=multipart_upload_id,
        )
        self.repo.create(upload)
        self._create_type_metadata(upload, file_type)
        log_action(self.repo.db, action="upload.multipart_initiated", user_id=user_id, entity_type="upload", entity_id=upload.id)
        self.repo.commit()

        total_parts = math.ceil(size_bytes / MULTIPART_PART_SIZE_BYTES) or 1
        return upload, multipart_upload_id, total_parts

    def _get_owned_multipart_upload(self, upload_id: uuid.UUID, user_id: uuid.UUID) -> Upload:
        """Shared ownership + "is this actually a multipart session"
        check used by part-url/complete/abort — one place, not three
        copies of the same two checks."""
        upload = self.get(upload_id, user_id)  # 404 if not found or not owned — existing anti-enumeration pattern
        if upload.multipart_upload_id is None:
            raise NotAMultipartUploadException("Bu ko'p qismli yuklash sessiyasi emas")
        return upload

    def get_part_upload_url(self, upload_id: uuid.UUID, user_id: uuid.UUID, part_number: int) -> str:
        if part_number < 1 or part_number > MULTIPART_MAX_PART_NUMBER:
            raise InvalidPartNumberException(f"part_number 1 dan {MULTIPART_MAX_PART_NUMBER} gacha bo'lishi kerak")
        upload = self._get_owned_multipart_upload(upload_id, user_id)
        return self.storage.create_presigned_part_url(
            upload.file_url, upload.multipart_upload_id, part_number, PRESIGNED_UPLOAD_TTL_SECONDS,
        )

    def complete_multipart_upload(self, upload_id: uuid.UUID, user_id: uuid.UUID, parts: list[tuple[int, str]]) -> Upload:
        if not parts:
            raise MissingPartsException("Kamida bitta qism kerak")
        upload = self._get_owned_multipart_upload(upload_id, user_id)

        s3_parts = [{"PartNumber": part_number, "ETag": etag} for part_number, etag in parts]
        self.storage.complete_multipart_upload(upload.file_url, upload.multipart_upload_id, s3_parts)

        upload.status = UPLOAD_STATUS_READY
        self.repo.commit()
        log_action(self.repo.db, action="upload.multipart_completed", user_id=user_id, entity_type="upload", entity_id=upload.id)
        return upload

    def abort_multipart_upload(self, upload_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Never leaves an orphaned active R2 multipart session — the
        abort call to R2 happens regardless of what we do to the local
        row afterward. The Upload row itself is marked FAILED (not
        soft-deleted) — its Image/Video/Document metadata row's FK
        stays valid, and a failed-upload row has the same audit value
        every other module's soft-delete convention already relies on."""
        upload = self._get_owned_multipart_upload(upload_id, user_id)
        self.storage.abort_multipart_upload(upload.file_url, upload.multipart_upload_id)
        upload.status = UPLOAD_STATUS_FAILED
        self.repo.commit()
        log_action(self.repo.db, action="upload.multipart_aborted", user_id=user_id, entity_type="upload", entity_id=upload.id)
