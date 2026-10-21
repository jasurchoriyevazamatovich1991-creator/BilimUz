"""Task 5 — grading exceptions (standard {success, message, data, errors} envelope)."""
from fastapi import status

from app.core.exceptions import AppException


class GradingItemNotFoundException(AppException):
    """Not a finished attempt, not a delivered manually graded question,
    or doesn't exist — one shape for all, no enumeration signal."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "GRADING_ITEM_NOT_FOUND"


class RubricNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "RUBRIC_NOT_FOUND"


class InvalidRubricException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_RUBRIC"


class RubricNotConfiguredException(AppException):
    """No rubric exists yet for the item's component."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "RUBRIC_NOT_CONFIGURED"


class InvalidCriterionScoresException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_CRITERION_SCORES"


class ReviewStateConflictException(AppException):
    """The requested action doesn't fit the item's review state (e.g. a
    draft owned by another grader, finalizing with no draft, editing a
    finalized grade without the revision flow)."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "REVIEW_STATE_CONFLICT"
