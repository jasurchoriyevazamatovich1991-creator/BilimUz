"""Unit tests for LearningCenterService — repository mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.learning_centers.exceptions import LearningCenterNotFoundException
from app.modules.learning_centers.schemas import LearningCenterCreateRequest, LearningCenterUpdateRequest
from app.modules.learning_centers.service import LearningCenterService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return LearningCenterService(mock_repo)


def test_create_succeeds_without_uniqueness_check(service, mock_repo):
    center = service.create_center(
        LearningCenterCreateRequest(name="Iqtidor", owner_name="Aziz Karimov", region="Toshkent"),
        actor_id=uuid.uuid4(),
    )
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()
    assert center.name == "Iqtidor"


def test_get_center_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(LearningCenterNotFoundException):
        service.get_center(uuid.uuid4())


def test_update_center_status(service, mock_repo):
    center_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=center_id)
    service.update_center(center_id, LearningCenterUpdateRequest(status="inactive"), actor_id=uuid.uuid4())
    mock_repo.update.assert_called_once()
    called_updates = mock_repo.update.call_args[0][1]
    assert called_updates["status"] == "inactive"


def test_delete_soft_deletes(service, mock_repo):
    center = MagicMock()
    mock_repo.get_by_id.return_value = center
    service.delete_center(center.id, actor_id=uuid.uuid4())
    mock_repo.soft_delete.assert_called_once_with(center)
    mock_repo.commit.assert_called_once()


def test_invalid_status_rejected_by_schema():
    with pytest.raises(ValueError):
        LearningCenterUpdateRequest(status="not-a-real-status")


@pytest.mark.parametrize("name", ["", "A", "A" * 256])
def test_invalid_name_length_rejected_by_schema(name):
    with pytest.raises(ValueError):
        LearningCenterCreateRequest(name=name)


def test_valid_institutional_phone_accepted():
    request = LearningCenterCreateRequest(name="Iqtidor", phone="+998712345678")
    assert request.phone == "+998712345678"


def test_invalid_phone_format_rejected():
    with pytest.raises(ValueError):
        LearningCenterCreateRequest(name="Iqtidor", phone="12345")


def test_owner_name_optional():
    request = LearningCenterCreateRequest(name="Iqtidor")
    assert request.owner_name is None


def test_owner_name_too_short_rejected():
    with pytest.raises(ValueError):
        LearningCenterCreateRequest(name="Iqtidor", owner_name="A")
