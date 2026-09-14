"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class LessonNotFoundForProgressException(AppException):
    """Raised when POST /lessons/{id}/complete targets a lesson_id that
    doesn't exist. Named distinctly from lessons/exceptions.py's own
    LessonNotFoundException — this module never imports that one,
    keeping the two modules' exceptions independent (matches the
    established pattern: uploads/exceptions.py's
    UploadNotFoundForMediaException is similarly named distinctly from
    uploads' own UploadNotFoundException)."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "LESSON_NOT_FOUND_FOR_PROGRESS"
