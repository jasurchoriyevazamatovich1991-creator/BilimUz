"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class TestNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "TEST_NOT_FOUND"


class InvalidTestReferenceException(AppException):
    """subject_id/grade_id/topic_id don't reference existing rows."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_TEST_REFERENCE"


class InvalidStatusTransitionException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "INVALID_STATUS_TRANSITION"


class CannotPublishEmptyTestException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "CANNOT_PUBLISH_EMPTY_TEST"
