"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class ResultNotFoundException(AppException):
    """Also covers 'exists but isn't yours' — same 404 for both, same
    resource-enumeration defense already used by auth/attempts."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "RESULT_NOT_FOUND"


class AttemptNotFinishedException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "ATTEMPT_NOT_FINISHED"


class InvalidRankingPeriodException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_RANKING_PERIOD"
