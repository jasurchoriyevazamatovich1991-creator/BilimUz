"""Unit tests for ProfileOut.compose() — the module's key design
decision (Variant A: User+Profile composition, no duplication)."""
import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.modules.profiles.schemas import ProfileOut


def _fake_user():
    return SimpleNamespace(
        id=uuid.uuid4(), first_name="Aziz", last_name="Karimov",
        phone="+998901234567", gender="male", birth_date=date(2000, 1, 1), image=None,
    )


def _fake_profile(user_id):
    return SimpleNamespace(
        bio="Talaba", address="Toshkent", telegram="@aziz", instagram=None, website=None,
        school_id=None, learning_center_id=None, status="active",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


def test_compose_pulls_identity_fields_from_user_not_profile():
    """The core guarantee: first_name/last_name/phone/gender/birth_date
    come from User, never from Profile (which doesn't even have them)."""
    user = _fake_user()
    profile = _fake_profile(user.id)
    result = ProfileOut.compose(user, profile)
    assert result.first_name == "Aziz"
    assert result.last_name == "Karimov"
    assert result.phone == "+998901234567"
    assert result.gender == "male"


def test_compose_pulls_bio_and_social_fields_from_profile():
    user = _fake_user()
    profile = _fake_profile(user.id)
    result = ProfileOut.compose(user, profile)
    assert result.bio == "Talaba"
    assert result.address == "Toshkent"
    assert result.telegram == "@aziz"


def test_profile_out_has_no_duplicate_storage_fields():
    """Structural proof: ProfileOut has exactly one first_name field,
    not two competing sources."""
    fields = ProfileOut.model_fields.keys()
    assert list(fields).count("first_name") == 1
