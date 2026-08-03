"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class UploadNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "UPLOAD_NOT_FOUND"


class UnsupportedFileTypeException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "UNSUPPORTED_FILE_TYPE"


class FileTooLargeException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "FILE_TOO_LARGE"
