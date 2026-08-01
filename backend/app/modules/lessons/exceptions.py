"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class LessonNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "LESSON_NOT_FOUND"


class InvalidTopicReferenceException(AppException):
    """Raised when a lesson is created/updated pointing at a topic_id
    that doesn't exist (or is soft-deleted) — same pattern as
    topics/exceptions.py's InvalidSubjectReferenceException."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_TOPIC_REFERENCE"


class EmptyLessonContentException(AppException):
    """A lesson must provide at least one of: video, pdf, content."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "EMPTY_LESSON_CONTENT"
