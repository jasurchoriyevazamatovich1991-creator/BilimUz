"""Unit tests for the strict password policy (Security Engineer spec)."""
import pytest

from app.modules.auth.validators import validate_password_strength


@pytest.mark.parametrize("password", [
    "short1!A",              # too short
    "alllowercase123!",       # no uppercase
    "ALLUPPERCASE123!",       # no lowercase
    "NoDigitsHere!!!!",       # no digit
    "NoSpecialChar1234",      # no special char
    "Password123456",         # long enough but no special char
])
def test_rejects_weak_passwords(password):
    with pytest.raises(ValueError):
        validate_password_strength(password)


def test_accepts_strong_password():
    strong = "Str0ng!Passw0rd#2026"
    assert validate_password_strength(strong) == strong


def test_rejects_common_weak_password():
    with pytest.raises(ValueError):
        validate_password_strength("Password123!")  # not in denylist itself, but too weak pattern-wise is fine
        validate_password_strength("Administrator1")
