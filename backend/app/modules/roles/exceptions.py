"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class RoleNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "ROLE_NOT_FOUND"


class RoleAlreadyExistsException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "ROLE_ALREADY_EXISTS"


class SystemRoleProtectedException(AppException):
    """Raised when someone tries to rename/delete one of the 8 seeded
    system roles — these are load-bearing for require_roles() checks
    across every module and must never change identity through the API."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "SYSTEM_ROLE_PROTECTED"


class RoleInUseException(AppException):
    """Raised when deleting a role that's still assigned to at least one
    user — deleting it would leave those users with a dangling role_id."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "ROLE_IN_USE"
