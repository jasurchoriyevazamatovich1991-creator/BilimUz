"""Unit tests for MeService — no DB, no mocks needed for the pure shaping
logic; a plain object with the right attributes is enough."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.modules.auth.me.service import MeService


def _fake_user(role=None):
    return SimpleNamespace(
        id=uuid.uuid4(), first_name="Aziz", last_name="Karimov",
        phone="+998901234567", email="aziz@example.com", status="active",
        role=role, created_at=datetime.now(timezone.utc),
    )


def test_get_profile_never_includes_password_hash():
    user = _fake_user()
    service = MeService()
    profile = service.get_profile(user)
    assert not hasattr(profile, "password_hash")
    assert "password" not in profile.model_dump()


def test_get_profile_includes_role_when_available():
    role = SimpleNamespace(id=uuid.uuid4(), name="Student")
    user = _fake_user(role=role)
    profile = MeService().get_profile(user)
    assert profile.role is not None
    assert profile.role.name == "Student"


def test_get_profile_role_is_none_when_unavailable():
    user = _fake_user(role=None)
    profile = MeService().get_profile(user)
    assert profile.role is None


def test_get_profile_preserves_core_fields():
    user = _fake_user()
    profile = MeService().get_profile(user)
    assert profile.id == user.id
    assert profile.first_name == "Aziz"
    assert profile.phone == "+998901234567"
    assert profile.status == "active"
