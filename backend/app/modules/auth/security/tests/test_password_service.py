"""Unit tests for PasswordService — no DB, no mocks needed (pure Argon2 +
regex logic)."""
import pytest

from app.modules.auth.security.password_service import PasswordService


@pytest.fixture
def service():
    return PasswordService()


def test_hash_is_not_plaintext(service):
    hashed = service.hash_password("Str0ng!Passw0rd")
    assert hashed != "Str0ng!Passw0rd"
    assert hashed.startswith("$argon2")


def test_verify_correct_password_succeeds(service):
    hashed = service.hash_password("Str0ng!Passw0rd")
    assert service.verify_password("Str0ng!Passw0rd", hashed) is True


def test_verify_wrong_password_fails(service):
    hashed = service.hash_password("Str0ng!Passw0rd")
    assert service.verify_password("Wrong!Password1", hashed) is False


def test_strong_password_has_no_errors(service):
    result = service.validate_password_strength("Str0ng!Passw0rd")
    assert result.is_valid is True
    assert result.errors == []


def test_short_password_reports_too_short(service):
    result = service.validate_password_strength("Ab1!")
    codes = [e.code for e in result.errors]
    assert "TOO_SHORT" in codes
    assert result.is_valid is False


def test_all_violations_reported_at_once(service):
    """The whole point of structured errors: one weak password should
    surface every broken rule, not just the first."""
    result = service.validate_password_strength("alllowercase")
    codes = {e.code for e in result.errors}
    assert codes == {"MISSING_UPPERCASE", "MISSING_DIGIT", "MISSING_SPECIAL_CHAR"}


def test_missing_only_special_char(service):
    result = service.validate_password_strength("Str0ngPassword")
    codes = [e.code for e in result.errors]
    assert codes == ["MISSING_SPECIAL_CHAR"]
