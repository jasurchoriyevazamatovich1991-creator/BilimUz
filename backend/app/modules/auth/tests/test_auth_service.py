"""
Unit tests for AuthService — repository is mocked, so these run without a
real database. Integration tests (with a real Postgres) belong in a
separate `test_auth_integration.py` (not included in this exemplar).
"""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from app.core.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    VerificationCodeInvalidException,
)
from app.core.security import hash_password, hash_verification_code


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return AuthService(mock_repo)


def test_register_raises_if_phone_taken(service, mock_repo):
    mock_repo.get_user_by_identifier.return_value = MagicMock()
    data = RegisterRequest(
        first_name="Aziz", last_name="Karimov", phone="+998901234567", password="parol123"
    )
    with pytest.raises(UserAlreadyExistsException):
        service.register(data)


def test_register_creates_user_and_code(service, mock_repo):
    mock_repo.get_user_by_identifier.return_value = None
    data = RegisterRequest(
        first_name="Aziz", last_name="Karimov", phone="+998901234567", password="parol123"
    )
    user, code = service.register(data)

    assert len(code) == 6 and code.isdigit()
    mock_repo.create_user.assert_called_once()
    mock_repo.create_verification_code.assert_called_once()
    mock_repo.commit.assert_called_once()


def test_login_raises_on_wrong_password(service, mock_repo):
    fake_user = MagicMock(password_hash=hash_password("correct-pass"))
    mock_repo.get_user_by_identifier.return_value = fake_user
    with pytest.raises(InvalidCredentialsException):
        service.login("+998901234567", "wrong-pass", ip=None, device=None)


def test_verify_raises_on_wrong_code(service, mock_repo):
    user_id = uuid.uuid4()
    mock_repo.get_user_by_id.return_value = MagicMock(id=user_id)
    mock_repo.get_active_verification_code.return_value = MagicMock(
        attempts=0, code_hash=hash_verification_code("111111")
    )
    with pytest.raises(VerificationCodeInvalidException):
        service.verify(user_id, "000000")


def test_change_password_rejects_wrong_current(service, mock_repo):
    from app.modules.auth.exceptions import CurrentPasswordIncorrectException

    user_id = uuid.uuid4()
    mock_repo.get_user_by_id.return_value = MagicMock(
        id=user_id, password_hash=hash_password("Correct!Passw0rd1")
    )
    with pytest.raises(CurrentPasswordIncorrectException):
        service.change_password(user_id, "Wrong!Passw0rd1", "New!Passw0rd12")


def test_change_password_rejects_reused_password(service, mock_repo):
    from app.modules.auth.exceptions import PasswordReuseException

    user_id = uuid.uuid4()
    old_hash = hash_password("Old!Passw0rd123")
    mock_repo.get_user_by_id.return_value = MagicMock(id=user_id, password_hash=old_hash)
    mock_repo.get_recent_password_hashes.return_value = [old_hash]
    with pytest.raises(PasswordReuseException):
        service.change_password(user_id, "Old!Passw0rd123", "Old!Passw0rd123")


def test_logout_all_devices_revokes_and_commits(service, mock_repo):
    mock_repo.revoke_all_refresh_tokens.return_value = 3
    count = service.logout_all_devices(uuid.uuid4())
    assert count == 3
    mock_repo.commit.assert_called()
