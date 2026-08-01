"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class TopicNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "TOPIC_NOT_FOUND"


class InvalidSubjectReferenceException(AppException):
    """Raised when a topic is created/updated pointing at a subject_id
    that doesn't exist (or is soft-deleted) — the FK constraint in the DB
    would catch this too, but failing here gives a clean 422 instead of
    a raw integrity-error 500."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_SUBJECT_REFERENCE"


class InvalidGradeReferenceException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_GRADE_REFERENCE"
