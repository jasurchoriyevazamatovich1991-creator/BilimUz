"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class ChatNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "CHAT_NOT_FOUND"


class StudyPlanNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "STUDY_PLAN_NOT_FOUND"


class AIProviderNotConfiguredException(AppException):
    """Raised by AIProvider.generate() when no real vendor is wired in —
    per the approved Sprint 9 scope (provider abstraction only). An
    honest refusal, not a fake response — see providers.py."""
    status_code = status.HTTP_501_NOT_IMPLEMENTED
    error_code = "AI_PROVIDER_NOT_CONFIGURED"
