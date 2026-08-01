"""
Unit tests for AuthService — repository is mocked, real PasswordService/
JWTService instances used (both stateless, no mocking needed). Updated in
Sprint 4 (Auth Cutover) for the new 3-arg constructor and the unified
core/security/ services.
"""
import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    VerificationCodeInvalidException,
)
from app.core.security.jwt_service import JWTService
from app.core.security.password_service import PasswordService
from app.core.security.verification import hash_verification_code
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService

STRONG_PASSWORD = "Str0ng!Passw0rd"  # 16 chars, upper/lower/digit/special — passes the 12-char policy


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
    return AuthService(mock_repo, password_service, jwt_service)


def test_register_raises_if_phone_taken(service, mock_repo):
    mock_repo.get_user_by_identifier.return_value = MagicMock()
    data = RegisterRequest(
        first_name="Aziz", last_name="Karimov", phone="+998901234567", password=STRONG_PASSWORD
    )
    with pytest.raises(UserAlreadyExistsException):
        service.register(data)


def test_register_creates_user_and_code(service, mock_repo):
    mock_repo.get_user_by_identifier.return_value = None
    data = RegisterRequest(
        first_name="Aziz", last_name="Karimov", phone="+998901234567", password=STRONG_PASSWORD
    )
    user, code = service.register(data)

    assert len(code) == 6 and code.isdigit()
    assert user.password_hash.startswith("$argon2")
    mock_repo.create_user.assert_called_once()
    mock_repo.create_verification_code.assert_called_once()
    mock_repo.commit.assert_called_once()


def test_login_raises_on_wrong_password(service, mock_repo, password_service):
    fake_user = MagicMock(password_hash=password_service.hash_password("Correct!Passw0rd1"))
    mock_repo.get_user_by_identifier.return_value = fake_user
    with pytest.raises(InvalidCredentialsException):
        service.login("+998901234567", "Wrong!Passw0rd2", ip=None, device=None)


def test_login_succeeds_and_issues_tokens(service, mock_repo, password_service):
    user_id = uuid.uuid4()
    fake_user = MagicMock(id=user_id, password_hash=password_service.hash_password(STRONG_PASSWORD))
    mock_repo.get_user_by_identifier.return_value = fake_user
    tokens = service.login("+998901234567", STRONG_PASSWORD, ip="127.0.0.1", device="pytest")
    assert tokens.access_token and tokens.refresh_token


def test_verify_raises_on_wrong_code(service, mock_repo):
    user_id = uuid.uuid4()
    mock_repo.get_user_by_id.return_value = MagicMock(id=user_id)
    mock_repo.get_active_verification_code.return_value = MagicMock(
        attempts=0, code_hash=hash_verification_code("111111")
    )
    with pytest.raises(VerificationCodeInvalidException):
        service.verify(user_id, "000000")


def test_change_password_rejects_wrong_current(service, mock_repo, password_service):
    from app.modules.auth.exceptions import CurrentPasswordIncorrectException

    user_id = uuid.uuid4()
    mock_repo.get_user_by_id.return_value = MagicMock(
        id=user_id, password_hash=password_service.hash_password("Correct!Passw0rd1")
    )
    with pytest.raises(CurrentPasswordIncorrectException):
        service.change_password(user_id, "Wrong!Passw0rd1", "New!StrongPassw0rd2")


def test_change_password_rejects_reused_password(service, mock_repo, password_service):
    from app.modules.auth.exceptions import PasswordReuseException

    user_id = uuid.uuid4()
    old_hash = password_service.hash_password("Old!Passw0rd123")
    mock_repo.get_user_by_id.return_value = MagicMock(id=user_id, password_hash=old_hash)
    mock_repo.get_recent_password_hashes.return_value = [old_hash]
    with pytest.raises(PasswordReuseException):
        service.change_password(user_id, "Old!Passw0rd123", "Old!Passw0rd123")


def test_change_password_rejects_weak_new_password(service, mock_repo, password_service):
    from app.modules.auth.exceptions import WeakPasswordException

    user_id = uuid.uuid4()
    mock_repo.get_user_by_id.return_value = MagicMock(
        id=user_id, password_hash=password_service.hash_password("Correct!Passw0rd1")
    )
    mock_repo.get_recent_password_hashes.return_value = []
    with pytest.raises(WeakPasswordException):
        service.change_password(user_id, "Correct!Passw0rd1", "weak")


def test_logout_all_devices_revokes_and_commits(service, mock_repo):
    mock_repo.revoke_all_refresh_tokens.return_value = 3
    count = service.logout_all_devices(uuid.uuid4())
    assert count == 3
    mock_repo.commit.assert_called()
