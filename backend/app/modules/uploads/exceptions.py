"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class UploadNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "UPLOAD_NOT_FOUND"


class UnsupportedFileTypeException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "UNSUPPORTED_FILE_TYPE"


class FileTooLargeException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "FILE_TOO_LARGE"


class LessonNotFoundException(AppException):
    """Sprint 27 — raised when a presigned session is requested with a
    lesson_id that doesn't exist."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "LESSON_NOT_FOUND"


class LessonUploadNotPermittedException(AppException):
    """Sprint 27 — raised when a non-Admin/Super Admin/Teacher user
    tries to create a lesson-linked upload. Matches Lessons' own write
    RBAC exactly (see lessons/router.py) — not a new, invented tier."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "LESSON_UPLOAD_NOT_PERMITTED"


class UploadNotReadyException(AppException):
    """Sprint 27 — raised when a view URL is requested for an upload
    that hasn't been finalized yet (still status=pending)."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "UPLOAD_NOT_READY"


class NotAMultipartUploadException(AppException):
    """Sprint 27 Amendment — raised when a part-url/complete/abort call
    targets an Upload row that was never initiated as a multipart
    session (multipart_upload_id is NULL)."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "NOT_A_MULTIPART_UPLOAD"


class InvalidPartNumberException(AppException):
    """Sprint 27 Amendment — part_number outside the valid 1..10000
    range (S3/R2's own hard limit)."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_PART_NUMBER"


class MissingPartsException(AppException):
    """Sprint 27 Amendment — complete-multipart called with an empty
    parts list."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "MISSING_PARTS"
