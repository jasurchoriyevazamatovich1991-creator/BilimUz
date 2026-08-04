"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class SystemLogNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "SYSTEM_LOG_NOT_FOUND"
