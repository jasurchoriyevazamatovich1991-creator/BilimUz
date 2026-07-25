"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class PermissionNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "PERMISSION_NOT_FOUND"


class PermissionAlreadyExistsException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "PERMISSION_ALREADY_EXISTS"


class RolePermissionAlreadyExistsException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "ROLE_PERMISSION_ALREADY_EXISTS"


class RolePermissionNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "ROLE_PERMISSION_NOT_FOUND"


class PermissionDeniedException(AppException):
    """Raised by require_permission() when the current user's role does
    not hold the required permission — distinct from require_roles()'s
    generic 403 so clients can tell 'wrong role' apart from 'right role,
    missing specific permission' if they ever need to."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "PERMISSION_DENIED"
