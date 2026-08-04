"""Unit tests for SchoolService — repository mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.schools.exceptions import SchoolNotFoundException
from app.modules.schools.schemas import SchoolCreateRequest, SchoolUpdateRequest
from app.modules.schools.service import SchoolService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return SchoolService(mock_repo)


def test_create_succeeds_without_uniqueness_check(service, mock_repo):
    """Unlike grades/subjects, school names are NOT required to be
    unique — two towns can each have a '1-maktab'."""
    school = service.create_school(SchoolCreateRequest(name="1-maktab", region="Toshkent"), actor_id=uuid.uuid4())
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()
    assert school.name == "1-maktab"


def test_get_school_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(SchoolNotFoundException):
        service.get_school(uuid.uuid4())


def test_update_school_status(service, mock_repo):
    school_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=school_id)
    service.update_school(school_id, SchoolUpdateRequest(status="inactive"), actor_id=uuid.uuid4())
    mock_repo.update.assert_called_once()
    called_updates = mock_repo.update.call_args[0][1]
    assert called_updates["status"] == "inactive"


def test_delete_soft_deletes(service, mock_repo):
    school = MagicMock()
    mock_repo.get_by_id.return_value = school
    service.delete_school(school.id, actor_id=uuid.uuid4())
    mock_repo.soft_delete.assert_called_once_with(school)
    mock_repo.commit.assert_called_once()


def test_invalid_status_rejected_by_schema():
    with pytest.raises(ValueError):
        SchoolUpdateRequest(status="not-a-real-status")


@pytest.mark.parametrize("name", ["", "A", "A" * 256])
def test_invalid_name_length_rejected_by_schema(name):
    with pytest.raises(ValueError):
        SchoolCreateRequest(name=name)


def test_valid_institutional_phone_accepted():
    request = SchoolCreateRequest(name="1-maktab", phone="+998712345678")
    assert request.phone == "+998712345678"


def test_invalid_phone_format_rejected():
    with pytest.raises(ValueError):
        SchoolCreateRequest(name="1-maktab", phone="12345")


def test_none_phone_is_allowed():
    request = SchoolCreateRequest(name="1-maktab")
    assert request.phone is None
