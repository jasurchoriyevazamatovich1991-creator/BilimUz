"""Unit tests for ProfileService — all repositories mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.profiles.exceptions import (
    InvalidLearningCenterReferenceException,
    InvalidSchoolReferenceException,
    ProfileNotFoundException,
)
from app.modules.profiles.schemas import ProfileListParams, ProfileUpdateRequest
from app.modules.profiles.service import ProfileService


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
    mock_user_repo.get_by_id.return_value = MagicMock(id=user_id)
    mock_repo.get_by_user_id.return_value = None

    service.get_profile(user_id)

    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()


def test_get_profile_does_not_recreate_existing_profile(service, mock_repo, mock_user_repo):
    user_id = uuid.uuid4()
    mock_user_repo.get_by_id.return_value = MagicMock(id=user_id)
    mock_repo.get_by_user_id.return_value = MagicMock(id=uuid.uuid4())

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
    mock_user_repo.get_by_id.return_value = MagicMock(id=user_id)
    mock_repo.get_by_user_id.return_value = MagicMock(id=uuid.uuid4())
    mock_school_repo.get_by_id.return_value = MagicMock()

    service.update_profile(user_id, ProfileUpdateRequest(school_id=uuid.uuid4(), bio="Yangi bio"), actor_id=user_id)

    mock_repo.update.assert_called_once()
    mock_repo.commit.assert_called_once()


def test_update_does_not_touch_school_repo_when_school_id_not_provided(service, mock_repo, mock_user_repo, mock_school_repo):
    user_id = uuid.uuid4()
    mock_user_repo.get_by_id.return_value = MagicMock(id=user_id)
    mock_repo.get_by_user_id.return_value = MagicMock(id=uuid.uuid4())

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
