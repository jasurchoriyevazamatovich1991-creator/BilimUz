"""Unit tests for the provider interfaces — proves the honest-refusal
behavior explicitly, not just by inspection."""
import pytest

from app.modules.notifications.exceptions import ProviderNotConfiguredException
from app.modules.notifications.providers import UnconfiguredEmailProvider, UnconfiguredSmsProvider


def test_unconfigured_email_provider_raises_not_silently_succeeds():
    provider = UnconfiguredEmailProvider()
    with pytest.raises(ProviderNotConfiguredException):
        provider.send("user@example.com", "Subject", "Body")


def test_unconfigured_sms_provider_raises_not_silently_succeeds():
    provider = UnconfiguredSmsProvider()
    with pytest.raises(ProviderNotConfiguredException):
        provider.send("+998901234567", "Message")


def test_provider_not_configured_exception_is_501():
    """A caller must be able to tell 'not implemented yet' apart from a
    generic 4xx validation error."""
    assert ProviderNotConfiguredException.status_code == 501
