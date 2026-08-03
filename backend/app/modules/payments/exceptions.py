"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class PlanNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "PLAN_NOT_FOUND"


class SubscriptionNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "SUBSCRIPTION_NOT_FOUND"


class PaymentNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "PAYMENT_NOT_FOUND"


class PaymentAlreadyRefundedException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "PAYMENT_ALREADY_REFUNDED"


class PaymentNotRefundableException(AppException):
    """Only a 'success' payment can be refunded — pending/failed/cancelled cannot."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "PAYMENT_NOT_REFUNDABLE"


class UnknownPaymentProviderException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "UNKNOWN_PAYMENT_PROVIDER"


class PaymentProviderNotConfiguredException(AppException):
    """Raised by PaymentProvider.initiate()/verify_webhook()/refund() when
    no real vendor is wired in — per the approved Sprint 9 scope
    (provider abstraction only). An honest refusal, not a fake success —
    see providers.py."""
    status_code = status.HTTP_501_NOT_IMPLEMENTED
    error_code = "PAYMENT_PROVIDER_NOT_CONFIGURED"
