"""Unit tests for JWTService — no DB, no FastAPI, pure PyJWT logic."""
import time
from datetime import timedelta

import jwt as pyjwt
import pytest

from app.modules.auth.jwt.jwt_service import JWTService
from app.modules.auth.jwt.schemas import TokenType


@pytest.fixture
def service():
    return JWTService(
        secret_key="test-secret-key-not-for-production",
        algorithm="HS256",
        access_expire_minutes=15,
        refresh_expire_days=30,
    )


def test_access_token_decodes_with_correct_claims(service):
    token = service.create_access_token(subject="user-123")
    payload = service.decode_token(token)

    assert payload.sub == "user-123"
    assert payload.type == TokenType.ACCESS
    assert payload.jti  # present and non-empty
    assert payload.exp > payload.iat


def test_refresh_token_has_longer_expiry_than_access(service):
    access = service.decode_token(service.create_access_token("user-1"))
    refresh = service.decode_token(service.create_refresh_token("user-1"))
    assert refresh.exp > access.exp


def test_each_token_gets_a_unique_jti(service):
    token1 = service.decode_token(service.create_access_token("user-1"))
    token2 = service.decode_token(service.create_access_token("user-1"))
    assert token1.jti != token2.jti


def test_verify_token_type_true_for_matching_type(service):
    payload = service.decode_token(service.create_access_token("user-1"))
    assert service.verify_token_type(payload, TokenType.ACCESS) is True


def test_verify_token_type_false_for_mismatched_type(service):
    payload = service.decode_token(service.create_refresh_token("user-1"))
    assert service.verify_token_type(payload, TokenType.ACCESS) is False


def test_decode_raises_on_expired_token(service):
    expired_service = JWTService(
        secret_key="test-secret-key-not-for-production",
        algorithm="HS256",
        access_expire_minutes=0,  # expires immediately
        refresh_expire_days=30,
    )
    token = expired_service.create_access_token("user-1")
    time.sleep(1)
    with pytest.raises(pyjwt.ExpiredSignatureError):
        expired_service.decode_token(token)


def test_decode_raises_on_tampered_signature(service):
    token = service.create_access_token("user-1")
    tampered = token[:-4] + "abcd"
    with pytest.raises(pyjwt.PyJWTError):
        service.decode_token(tampered)


def test_decode_raises_on_wrong_secret():
    signer = JWTService("secret-a", "HS256", 15, 30)
    verifier = JWTService("secret-b", "HS256", 15, 30)
    token = signer.create_access_token("user-1")
    with pytest.raises(pyjwt.InvalidSignatureError):
        verifier.decode_token(token)
