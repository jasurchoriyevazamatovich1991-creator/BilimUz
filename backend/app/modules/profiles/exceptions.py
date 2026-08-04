"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class ProfileNotFoundException(AppException):
    """Also covers 'exists but isn't yours' for the /me path — same
    resource-enumeration defense used platform-wide."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "PROFILE_NOT_FOUND"


class InvalidSchoolReferenceException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_SCHOOL_REFERENCE"


class InvalidLearningCenterReferenceException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_LEARNING_CENTER_REFERENCE"
