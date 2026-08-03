"""Unit tests for EncryptionService — real Fernet round-trip, no mocks
needed since it's pure crypto logic."""
import pytest
from cryptography.fernet import Fernet

from app.core.security.encryption import EncryptionService


@pytest.fixture
def service():
    return EncryptionService(key=Fernet.generate_key().decode())


def test_encrypt_produces_different_output_than_plaintext(service):
    ciphertext = service.encrypt("my-secret-password")
    assert ciphertext != "my-secret-password"


def test_decrypt_recovers_original_plaintext(service):
    ciphertext = service.encrypt("sk_live_abc123")
    assert service.decrypt(ciphertext) == "sk_live_abc123"


def test_encrypting_same_value_twice_produces_different_ciphertext(service):
    """Fernet includes a random IV/timestamp — same plaintext, different
    ciphertext each time. Confirms we're not using a naive deterministic scheme."""
    c1 = service.encrypt("same-value")
    c2 = service.encrypt("same-value")
    assert c1 != c2
    assert service.decrypt(c1) == service.decrypt(c2) == "same-value"


def test_decrypt_with_wrong_key_raises():
    encryptor = EncryptionService(key=Fernet.generate_key().decode())
    decryptor = EncryptionService(key=Fernet.generate_key().decode())
    ciphertext = encryptor.encrypt("secret")
    with pytest.raises(ValueError):
        decryptor.decrypt(ciphertext)


def test_decrypt_garbage_input_raises(service):
    with pytest.raises(ValueError):
        service.decrypt("not-a-real-fernet-token")
