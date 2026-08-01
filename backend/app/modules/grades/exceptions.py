"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class GradeNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "GRADE_NOT_FOUND"


class GradeAlreadyExistsException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "GRADE_ALREADY_EXISTS"
