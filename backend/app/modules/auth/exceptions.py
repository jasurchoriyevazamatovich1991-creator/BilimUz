"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class WeakPasswordException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "WEAK_PASSWORD"


class PasswordReuseException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "PASSWORD_REUSED"


class CurrentPasswordIncorrectException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "CURRENT_PASSWORD_INCORRECT"


class DeviceNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "DEVICE_NOT_FOUND"
