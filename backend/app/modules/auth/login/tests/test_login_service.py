"""Unit tests for LoginService — repository mocked, real PasswordService/
JWTService instances used (stateless, no mocking needed)."""
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import InvalidCredentialsException
from app.modules.auth.jwt.jwt_service import JWTService
from app.modules.auth.login.service import LoginService
from app.modules.auth.security.password_service import PasswordService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def password_service():
    return PasswordService()


@pytest.fixture
def jwt_service():
    return JWTService("test-secret", "HS256", access_expire_minutes=15, refresh_expire_days=30)


@pytest.fixture
def service(mock_repo, password_service, jwt_service):
    return LoginService(mock_repo, password_service, jwt_service)


def test_login_rejects_unknown_email(service, mock_repo):
    mock_repo.get_user_by_identifier.return_value = None
    with pytest.raises(InvalidCredentialsException):
        service.login("nobody@example.com", "whatever", ip=None, device=None)


def test_login_rejects_wrong_password(service, mock_repo, password_service):
    correct_hash = password_service.hash_password("Correct!Passw0rd1")
    mock_repo.get_user_by_identifier.return_value = MagicMock(password_hash=correct_hash)
    with pytest.raises(InvalidCredentialsException):
        service.login("user@example.com", "Wrong!Password2", ip=None, device=None)


def test_login_rejects_bcrypt_hash_gracefully(service, mock_repo):
    """A user registered via the OLD bcrypt system must not crash this
    endpoint — must fail closed as InvalidCredentialsException, same as
    UnknownHashError test target for _verify()."""
    bcrypt_style_hash = "$2b$12$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWX"
    mock_repo.get_user_by_identifier.return_value = MagicMock(password_hash=bcrypt_style_hash)
    with pytest.raises(InvalidCredentialsException):
        service.login("user@example.com", "AnyPassword1!", ip=None, device=None)


def test_login_succeeds_with_correct_credentials(service, mock_repo, password_service):
    correct_hash = password_service.hash_password("Correct!Passw0rd1")
    user_id = "11111111-1111-1111-1111-111111111111"
    mock_repo.get_user_by_identifier.return_value = MagicMock(id=user_id, password_hash=correct_hash)

    response = service.login("user@example.com", "Correct!Passw0rd1", ip="127.0.0.1", device="pytest")

    assert response.access_token and response.refresh_token
    assert response.token_type == "bearer"
    mock_repo.commit.assert_called_once()


def test_login_response_includes_expiration_metadata(service, mock_repo, password_service):
    correct_hash = password_service.hash_password("Correct!Passw0rd1")
    mock_repo.get_user_by_identifier.return_value = MagicMock(id="u1", password_hash=correct_hash)

    response = service.login("user@example.com", "Correct!Passw0rd1", ip=None, device=None)

    assert response.access_token_expires_in == 15 * 60
    assert response.refresh_token_expires_in == 30 * 24 * 60 * 60
    assert response.access_token_expires_at is not None
    assert response.refresh_token_expires_at is not None


def test_login_persists_refresh_token_and_records_history(service, mock_repo, password_service):
    correct_hash = password_service.hash_password("Correct!Passw0rd1")
    mock_repo.get_user_by_identifier.return_value = MagicMock(id="u1", password_hash=correct_hash)

    service.login("user@example.com", "Correct!Passw0rd1", ip="1.2.3.4", device="pytest-agent")

    mock_repo.create_refresh_token.assert_called_once()
    mock_repo.record_login.assert_called_once()
