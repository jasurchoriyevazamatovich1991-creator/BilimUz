"""Unit tests for pure validation functions — no I/O."""
import pytest

from app.modules.payments.validators import (
    validate_amount,
    validate_currency,
    validate_duration_days,
    validate_plan_name,
    validate_provider,
)


def test_valid_amount_passes():
    assert validate_amount(100.0) == 100.0


def test_zero_amount_rejected():
    with pytest.raises(ValueError):
        validate_amount(0)


def test_negative_amount_rejected():
    with pytest.raises(ValueError):
        validate_amount(-5)


def test_valid_currency_passes():
    assert validate_currency("UZS") == "UZS"


def test_invalid_currency_rejected():
    with pytest.raises(ValueError):
        validate_currency("USD")


def test_valid_provider_passes():
    assert validate_provider("click") == "click"


def test_invalid_provider_rejected():
    with pytest.raises(ValueError):
        validate_provider("paypal")


def test_valid_plan_name_passes():
    assert validate_plan_name("  Premium  ") == "Premium"


def test_empty_plan_name_rejected():
    with pytest.raises(ValueError):
        validate_plan_name("")


def test_valid_duration_passes():
    assert validate_duration_days(30) == 30


def test_zero_duration_rejected():
    with pytest.raises(ValueError):
        validate_duration_days(0)
