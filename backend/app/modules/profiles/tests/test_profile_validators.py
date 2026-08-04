"""Unit tests for pure validation functions — no I/O."""
import pytest

from app.modules.profiles.constants import MAX_BIO_LENGTH
from app.modules.profiles.validators import validate_bio, validate_social_handle, validate_website


def test_valid_bio_passes():
    assert validate_bio("  Talaba, matematika  ") == "Talaba, matematika"


def test_bio_over_max_length_rejected():
    with pytest.raises(ValueError):
        validate_bio("x" * (MAX_BIO_LENGTH + 1))


def test_none_bio_allowed():
    assert validate_bio(None) is None


def test_social_handle_strips_leading_at_sign():
    assert validate_social_handle("@username") == "username"


def test_website_none_allowed():
    assert validate_website(None) is None
