"""
PaymentProvider interface — infrastructure used by PaymentService, same
relationship AIProvider/EmailProvider/StorageBackend have to their
respective services. NOT a new architectural layer.

Per the approved Sprint 9 scope: NO vendor SDK (Payme, Click, Stripe, or
any other) is imported anywhere in this module. UnconfiguredPaymentProvider
is the only implementation — it honestly raises rather than pretending
to initiate a payment, verify a webhook, or process a refund. A future
sprint adds a real implementation (e.g. PaymeProvider, ClickProvider) and
wires it in via a provider registry — zero change to PaymentService.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.modules.payments.exceptions import PaymentProviderNotConfiguredException, UnknownPaymentProviderException


@dataclass
class PaymentInitResult:
    redirect_url: str
    provider_reference: str


@dataclass
class WebhookVerificationResult:
    payment_id: str
    provider_txn_id: str
    is_success: bool
    raw_payload: dict


@dataclass
class RefundResult:
    provider_refund_reference: str
    raw_payload: dict


class PaymentProvider(ABC):
    @abstractmethod
    def initiate(self, amount: float, currency: str, payment_id: str) -> PaymentInitResult:
        """Raises on any failure (including 'not configured')."""
        ...

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: dict) -> WebhookVerificationResult:
        """Verifies the provider's signature and parses the payload.
        Raises if verification fails OR if not configured — an
        unconfigured provider must never accept an unverified webhook."""
        ...

    @abstractmethod
    def refund(self, provider_txn_id: str, amount: float) -> RefundResult:
        """Full-amount refunds only this sprint (approved decision)."""
        ...


class UnconfiguredPaymentProvider(PaymentProvider):
    """The only PaymentProvider implementation this sprint. Honest, not
    fake: real vendor integration is explicitly deferred (see module
    docstring). Refusing to verify webhooks by default is also the SAFE
    default — an unconfigured provider must never accept unverified
    external input."""

    def initiate(self, amount: float, currency: str, payment_id: str) -> PaymentInitResult:
        raise PaymentProviderNotConfiguredException(
            "To'lov provayderi ulanmagan — haqiqiy vendor integratsiyasi keyingi sprintga qoldirilgan"
        )

    def verify_webhook(self, raw_body: bytes, headers: dict) -> WebhookVerificationResult:
        raise PaymentProviderNotConfiguredException(
            "To'lov provayderi ulanmagan — webhook tekshirilmadi"
        )

    def refund(self, provider_txn_id: str, amount: float) -> RefundResult:
        raise PaymentProviderNotConfiguredException(
            "To'lov provayderi ulanmagan — qaytarish amalga oshirilmadi"
        )


class PaymentProviderRegistry:
    """Dispatches by provider name (e.g. 'click', 'payme') to the
    matching PaymentProvider instance — used by the webhook endpoint,
    which receives the provider name as a path parameter. Every provider
    this sprint resolves to the same UnconfiguredPaymentProvider."""

    def __init__(self, providers: dict[str, PaymentProvider]):
        self._providers = providers

    def get(self, provider_name: str) -> PaymentProvider:
        provider = self._providers.get(provider_name)
        if provider is None:
            raise UnknownPaymentProviderException(f"Noma'lum to'lov provayderi: {provider_name}")
        return provider
