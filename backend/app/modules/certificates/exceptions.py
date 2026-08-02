"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class CertificateNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "CERTIFICATE_NOT_FOUND"


class CannotCertifyFailedResultException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "CANNOT_CERTIFY_FAILED_RESULT"


class TemplateNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "TEMPLATE_NOT_FOUND"


class InvalidVerificationCodeException(AppException):
    """Deliberately generic — never reveals whether a code was 'close'
    to a real one, same anti-enumeration reasoning used everywhere else."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "INVALID_VERIFICATION_CODE"
