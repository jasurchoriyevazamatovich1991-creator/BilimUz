"""Unit tests for RefreshService — repository mocked, real JWTService used."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import InvalidTokenException
from app.core.security import hash_refresh_token
from app.modules.auth.jwt.jwt_service import JWTService
from app.modules.auth.refresh.service import RefreshService


@pytest.fixture
def jwt_service():
    return JWTService("test-secret", "HS256", access_expire_minutes=15, refresh_expire_days=30)


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, jwt_service):
    return RefreshService(mock_repo, jwt_service)


def test_refresh_rejects_malformed_token(service):
    with pytest.raises(InvalidTokenException):
        service.refresh("not-a-real-jwt-at-all")


def test_refresh_rejects_access_token_used_as_refresh(service, jwt_service, mock_repo):
    access_token = jwt_service.create_access_token(subject=str(uuid.uuid4()))
    with pytest.raises(InvalidTokenException):
        service.refresh(access_token)


def test_refresh_rejects_unknown_jti(service, jwt_service, mock_repo):
    refresh_token = jwt_service.create_refresh_token(subject=str(uuid.uuid4()))
    mock_repo.get_refresh_token_by_jti.return_value = None
    with pytest.raises(InvalidTokenException):
        service.refresh(refresh_token)


def test_refresh_rejects_hash_mismatch(service, jwt_service, mock_repo):
    """Simulates a token whose jti matches a stored row but whose actual
    string doesn't hash to the stored value — e.g. a forged/edited token
    that somehow reused a jti."""
    refresh_token = jwt_service.create_refresh_token(subject=str(uuid.uuid4()))
    mock_repo.get_refresh_token_by_jti.return_value = MagicMock(token_hash="wrong-hash-value")
    with pytest.raises(InvalidTokenException):
        service.refresh(refresh_token)


def test_refresh_rejects_old_system_token_missing_nbf_claim(service):
    """The specific compatibility gap flagged before writing this module:
    an old-system-issued token (no 'nbf' claim) must fail cleanly, not
    crash with an unhandled pydantic.ValidationError."""
    import jwt as pyjwt
    old_style_payload = {
        "sub": str(uuid.uuid4()), "type": "refresh", "iat": 1700000000, "exp": 1700003600, "jti": "abc123",
    }
    old_style_token = pyjwt.encode(old_style_payload, "test-secret", algorithm="HS256")
    with pytest.raises(InvalidTokenException):
        service.refresh(old_style_token)


def test_refresh_succeeds_and_rotates_token(service, jwt_service, mock_repo):
    user_id = uuid.uuid4()
    refresh_token = jwt_service.create_refresh_token(subject=str(user_id))
    payload = jwt_service.decode_token(refresh_token)

    stored = MagicMock(token_hash=hash_refresh_token(refresh_token), jti=payload.jti)
    mock_repo.get_refresh_token_by_jti.return_value = stored

    response = service.refresh(refresh_token)

    mock_repo.revoke_refresh_token.assert_called_once_with(stored)  # old token revoked
    mock_repo.create_refresh_token.assert_called_once()              # new token persisted
    mock_repo.commit.assert_called_once()
    assert response.refresh_token != refresh_token  # genuinely rotated, not reused
    assert response.access_token_expires_in == 15 * 60
