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


class ExamSectionNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "EXAM_SECTION_NOT_FOUND"


class ExamModuleNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "EXAM_MODULE_NOT_FOUND"


class DuplicateOrderNumberException(AppException):
    """order_number already used by a sibling row under the same
    parent (test for ExamSection, section for ExamModule) — the exact
    condition UNIQUE(test_id/section_id, order_number) enforces at the
    DB level; this exception lets the service layer surface it as a
    clean 409 instead of a raw IntegrityError."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "DUPLICATE_ORDER_NUMBER"
