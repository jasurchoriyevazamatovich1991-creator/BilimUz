"""Unit tests for pure validation functions — no I/O."""
import pytest

from app.modules.settings.validators import validate_port, validate_secret_value, validate_setting_key


def test_valid_key_passes():
    assert validate_setting_key("  site_name  ") == "site_name"


def test_empty_key_rejected():
    with pytest.raises(ValueError):
        validate_setting_key("")


@pytest.mark.parametrize("port", [0, -1, 65536, 100000])
def test_invalid_port_rejected(port):
    with pytest.raises(ValueError):
        validate_port(port)


def test_valid_port_passes():
    assert validate_port(587) == 587


def test_empty_secret_rejected():
    with pytest.raises(ValueError):
        validate_secret_value("")
