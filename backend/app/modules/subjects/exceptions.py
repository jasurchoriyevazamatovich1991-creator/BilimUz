"""Module-local exceptions — inherit from the shared AppException so the
global handler in core/exceptions.py still produces the standard envelope."""
from fastapi import status

from app.core.exceptions import AppException


class SubjectNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "SUBJECT_NOT_FOUND"


class SubjectAlreadyExistsException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "SUBJECT_ALREADY_EXISTS"


class SubjectValidationException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "SUBJECT_VALIDATION_ERROR"
