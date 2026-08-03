"""Unit tests for pure validation functions — no I/O."""
import pytest

from app.modules.notifications.validators import (
    validate_channel,
    validate_email_address,
    validate_phone_for_sms,
    validate_template_code,
    validate_title,
)


def test_valid_channel_passes():
    assert validate_channel("email") == "email"


def test_invalid_channel_rejected():
    with pytest.raises(ValueError):
        validate_channel("carrier_pigeon")


def test_valid_email_passes():
    assert validate_email_address("user@example.com") == "user@example.com"


def test_invalid_email_rejected():
    with pytest.raises(ValueError):
        validate_email_address("not-an-email")


def test_valid_uzbek_phone_passes_via_reused_validator():
    assert validate_phone_for_sms("+998901234567") == "+998901234567"


def test_invalid_phone_rejected():
    with pytest.raises(ValueError):
        validate_phone_for_sms("12345")


def test_empty_title_rejected():
    with pytest.raises(ValueError):
        validate_title("")


def test_empty_template_code_rejected():
    with pytest.raises(ValueError):
        validate_template_code("   ")
