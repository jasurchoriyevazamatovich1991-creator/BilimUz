"""Unit tests for the PaymentProvider interface and registry — proves
the honest-refusal behavior explicitly, same pattern as every Sprint 8/9
provider test."""
import pytest

from app.modules.payments.exceptions import PaymentProviderNotConfiguredException, UnknownPaymentProviderException
from app.modules.payments.providers import PaymentProviderRegistry, UnconfiguredPaymentProvider


def test_unconfigured_provider_initiate_raises():
    provider = UnconfiguredPaymentProvider()
    with pytest.raises(PaymentProviderNotConfiguredException):
        provider.initiate(1000, "UZS", "payment-id")


def test_unconfigured_provider_verify_webhook_raises():
    """The SAFE default — an unconfigured provider must never accept an
    unverified webhook."""
    provider = UnconfiguredPaymentProvider()
    with pytest.raises(PaymentProviderNotConfiguredException):
        provider.verify_webhook(b"{}", {})


def test_unconfigured_provider_refund_raises():
    provider = UnconfiguredPaymentProvider()
    with pytest.raises(PaymentProviderNotConfiguredException):
        provider.refund("txn-123", 1000)


def test_registry_dispatches_by_provider_name():
    provider = UnconfiguredPaymentProvider()
    registry = PaymentProviderRegistry({"click": provider})
    assert registry.get("click") is provider


def test_registry_rejects_unknown_provider():
    registry = PaymentProviderRegistry({"click": UnconfiguredPaymentProvider()})
    with pytest.raises(UnknownPaymentProviderException):
        registry.get("paypal")


def test_provider_not_configured_exception_is_501():
    assert PaymentProviderNotConfiguredException.status_code == 501
