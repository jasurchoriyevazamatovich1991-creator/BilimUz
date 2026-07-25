"""Validator edge cases for permission codes and module names."""
import pytest

from app.modules.permissions.validators import validate_module_name, validate_permission_code


@pytest.mark.parametrize("code,expected", [
    ("create_test", "CREATE_TEST"),
    ("CREATE_TEST", "CREATE_TEST"),
    ("view_analytics", "VIEW_ANALYTICS"),
])
def test_code_is_normalized_to_upper(code, expected):
    assert validate_permission_code(code) == expected


@pytest.mark.parametrize("code", ["1CREATE_TEST", "create-test", "create test", "_LEADING_UNDERSCORE"])
def test_invalid_codes_rejected(code):
    with pytest.raises(ValueError):
        validate_permission_code(code)


def test_known_module_accepted():
    assert validate_module_name("Tests") == "tests"


def test_unknown_module_rejected():
    with pytest.raises(ValueError):
        validate_module_name("not_a_real_module")
