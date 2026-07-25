"""
Module-local exceptions. UserNotFoundException already exists in
core/exceptions.py (used by auth) — reused here via re-export so both
modules raise the exact same exception type for "no such user", instead
of two classes that mean the same thing.
"""
from fastapi import status

from app.core.exceptions import AppException, UserNotFoundException  # noqa: F401  (re-exported)


class CannotModifySelfException(AppException):
    """Raised when an admin tries to change their own role/status through
    the admin endpoint — self-service changes go through /auth/me or
    /users/me instead, so privilege changes always have a second actor."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "CANNOT_MODIFY_SELF"


class InvalidRoleAssignmentException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_ROLE_ASSIGNMENT"
