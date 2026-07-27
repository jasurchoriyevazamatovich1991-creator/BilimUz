"""Unit tests for RegistrationService — repository mocked, real
PasswordService/JWTService instances used (both are stateless/pure, so
no mocking needed — this also proves the two new services actually
integrate correctly, not just in isolation)."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import UserAlreadyExistsException
from app.modules.auth.exceptions import WeakPasswordException
from app.modules.auth.jwt.jwt_service import JWTService
from app.modules.auth.registration.schemas import RegistrationRequest
from app.modules.auth.registration.service import RegistrationService
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
    return RegistrationService(mock_repo, password_service, jwt_service)


VALID_REQUEST = RegistrationRequest(
    first_name="Aziz", last_name="Karimov", phone="+998901234567", password="Str0ng!Passw0rd",
)


def test_register_rejects_duplicate_phone(service, mock_repo):
    mock_repo.get_user_by_identifier.return_value = MagicMock()
    with pytest.raises(UserAlreadyExistsException):
        service.register(VALID_REQUEST)


def test_register_rejects_weak_password(service, mock_repo):
    mock_repo.get_user_by_identifier.return_value = None
    weak_request = RegistrationRequest(
        first_name="Aziz", last_name="Karimov", phone="+998901234567", password="weak",
    )
    with pytest.raises(WeakPasswordException) as exc_info:
        service.register(weak_request)
    assert len(exc_info.value.errors) > 1  # structured, multiple violations reported


def test_register_creates_user_with_hashed_password(service, mock_repo):
    mock_repo.get_user_by_identifier.return_value = None
    user, tokens = service.register(VALID_REQUEST)

    mock_repo.create_user.assert_called_once()
    created_user = mock_repo.create_user.call_args[0][0]
    assert created_user.password_hash != "Str0ng!Passw0rd"
    assert created_user.password_hash.startswith("$argon2")


def test_register_issues_valid_token_pair(service, mock_repo, jwt_service):
    mock_repo.get_user_by_identifier.return_value = None
    user, tokens = service.register(VALID_REQUEST)

    assert tokens.access_token and tokens.refresh_token
    payload = jwt_service.decode_token(tokens.access_token)
    assert payload.type == "access"


def test_register_persists_refresh_token(service, mock_repo):
    mock_repo.get_user_by_identifier.return_value = None
    service.register(VALID_REQUEST)
    mock_repo.create_refresh_token.assert_called_once()
    mock_repo.commit.assert_called_once()
