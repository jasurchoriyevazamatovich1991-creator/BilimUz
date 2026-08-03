"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class NotificationNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOTIFICATION_NOT_FOUND"


class TemplateCodeAlreadyExistsException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "TEMPLATE_CODE_ALREADY_EXISTS"


class ProviderNotConfiguredException(AppException):
    """Raised by a provider interface's send() when no real provider is
    wired in — per the approved Sprint 8 scope (queue/trigger
    architecture + interfaces only, no real SMTP/SMS). This is an
    HONEST signal, not a fake success: the queue row stays 'pending',
    nothing is silently marked 'sent' when nothing was actually sent."""
    status_code = status.HTTP_501_NOT_IMPLEMENTED
    error_code = "PROVIDER_NOT_CONFIGURED"
