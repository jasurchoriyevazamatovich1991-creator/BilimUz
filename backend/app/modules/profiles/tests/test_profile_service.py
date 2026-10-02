"""Unit tests for ProfileService — all repositories mocked, no real DB needed."""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.modules.profiles.exceptions import (
    InvalidLearningCenterReferenceException,
    InvalidSchoolReferenceException,
    ProfileNotFoundException,
)
from app.modules.profiles.schemas import ProfileListParams, ProfileUpdateRequest
from app.modules.profiles.service import ProfileService
from app.modules.roles.models import Role  # noqa: F401 — side-effect import only: registers Role with
# SQLAlchemy's mapper registry before any Profile(...)/User-adjacent construction below,
# needed because this test file's own isolated import chain never otherwise imports roles/models.py
# (production always does, transitively, via app.main's full router tree).


def _fake_user(user_id: uuid.UUID) -> MagicMock:
    """Sprint 72 (TEST-1) — ProfileOut.compose() (schemas.py) reads
    every one of these fields and validates them through Pydantic, so
    an unconfigured MagicMock attribute (itself a MagicMock, not a
    valid str/date/None) fails validation. This was previously masked
    entirely: before the `Role` import above was added, every test
    that reached compose() failed earlier still, with a SQLAlchemy
    mapper-configuration error on the real Profile(...) construction in
    ProfileService._get_or_create(). Fixing that import let these
    tests run far enough to reveal this second, independent gap."""
    return MagicMock(id=user_id, first_name="Aziz", last_name="Aliyev", phone=None, gender=None, birth_date=None, image=None)


def _fake_profile(**overrides) -> MagicMock:
    """Same reasoning as _fake_user() above, for the Profile side of
    ProfileOut.compose() — used where the test supplies an
    already-existing Profile as a plain mock (not the real ORM object
    ProfileService._get_or_create() constructs for the lazy-create
    path, which _populate_created_profile() below handles instead)."""
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(), bio=None, address=None, telegram=None, instagram=None,
        website=None, school_id=None, learning_center_id=None, status="active",
        created_at=now, updated_at=now,
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


def _populate_created_profile(profile, _data=None) -> None:
    """Sprint 72 (TEST-1) — mock_repo.create() side_effect for the
    lazy-create path (test_get_profile_lazily_creates_missing_profile).
    ProfileService._get_or_create() constructs a REAL Profile(...) ORM
    object (not a mock) when no profile exists yet, then passes it to
    self.repo.create()/self.repo.commit() — both mocked here, so unlike
    production (where the real repository's db.add()+db.flush()/commit()
    resolves id/status/created_at/updated_at from the column defaults
    in mixins.py), those fields are never populated. This mirrors that
    resolution so ProfileOut.compose() validates exactly as it would
    against a genuinely flushed row."""
    now = datetime.now(timezone.utc)
    profile.status = "active"
    profile.created_at = now
    profile.updated_at = now


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_user_repo():
    return MagicMock()


@pytest.fixture
def mock_school_repo():
    return MagicMock()


@pytest.fixture
def mock_lc_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_user_repo, mock_school_repo, mock_lc_repo):
    return ProfileService(mock_repo, mock_user_repo, mock_school_repo, mock_lc_repo)


def test_get_profile_raises_when_user_missing(service, mock_user_repo):
    mock_user_repo.get_by_id.return_value = None
    with pytest.raises(ProfileNotFoundException):
        service.get_profile(uuid.uuid4())


def test_get_profile_lazily_creates_missing_profile(service, mock_repo, mock_user_repo):
    """The lazy get-or-create pattern — a user who registered before
    this module existed still gets a working profile on first access."""
    user_id = uuid.uuid4()
    mock_user_repo.get_by_id.return_value = _fake_user(user_id)
    mock_repo.get_by_user_id.return_value = None
    mock_repo.create.side_effect = _populate_created_profile

    service.get_profile(user_id)

    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()


def test_get_profile_does_not_recreate_existing_profile(service, mock_repo, mock_user_repo):
    user_id = uuid.uuid4()
    mock_user_repo.get_by_id.return_value = _fake_user(user_id)
    mock_repo.get_by_user_id.return_value = _fake_profile()

    service.get_profile(user_id)

    mock_repo.create.assert_not_called()


def test_update_rejects_invalid_school_reference(service, mock_repo, mock_user_repo, mock_school_repo):
    user_id = uuid.uuid4()
    mock_user_repo.get_by_id.return_value = MagicMock(id=user_id)
    mock_repo.get_by_user_id.return_value = MagicMock(id=uuid.uuid4())
    mock_school_repo.get_by_id.return_value = None

    with pytest.raises(InvalidSchoolReferenceException):
        service.update_profile(user_id, ProfileUpdateRequest(school_id=uuid.uuid4()), actor_id=user_id)


def test_update_rejects_invalid_learning_center_reference(service, mock_repo, mock_user_repo, mock_lc_repo):
    user_id = uuid.uuid4()
    mock_user_repo.get_by_id.return_value = MagicMock(id=user_id)
    mock_repo.get_by_user_id.return_value = MagicMock(id=uuid.uuid4())
    mock_lc_repo.get_by_id.return_value = None

    with pytest.raises(InvalidLearningCenterReferenceException):
        service.update_profile(user_id, ProfileUpdateRequest(learning_center_id=uuid.uuid4()), actor_id=user_id)


def test_update_succeeds_with_valid_references(service, mock_repo, mock_user_repo, mock_school_repo):
    user_id = uuid.uuid4()
    mock_user_repo.get_by_id.return_value = _fake_user(user_id)
    mock_repo.get_by_user_id.return_value = _fake_profile()
    mock_school_repo.get_by_id.return_value = MagicMock()

    service.update_profile(user_id, ProfileUpdateRequest(school_id=uuid.uuid4(), bio="Yangi bio"), actor_id=user_id)

    mock_repo.update.assert_called_once()
    mock_repo.commit.assert_called_once()


def test_update_does_not_touch_school_repo_when_school_id_not_provided(service, mock_repo, mock_user_repo, mock_school_repo):
    user_id = uuid.uuid4()
    mock_user_repo.get_by_id.return_value = _fake_user(user_id)
    mock_repo.get_by_user_id.return_value = _fake_profile()

    service.update_profile(user_id, ProfileUpdateRequest(bio="Faqat bio"), actor_id=user_id)

    mock_school_repo.get_by_id.assert_not_called()


def test_list_profiles_skips_orphaned_profile_defensively(service, mock_repo, mock_user_repo):
    """A profile whose user_id doesn't resolve (shouldn't happen, FK
    CASCADE prevents it) is skipped rather than crashing the whole list."""
    orphan_profile = MagicMock(user_id=uuid.uuid4())
    mock_repo.list.return_value = ([orphan_profile], 1)
    mock_user_repo.get_by_id.return_value = None

    items, total = service.list_profiles(ProfileListParams())

    assert items == []
    assert total == 1  # total count reflects the DB truth, not the filtered display list
