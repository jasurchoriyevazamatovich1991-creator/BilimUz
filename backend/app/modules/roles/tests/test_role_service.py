"""Unit tests for RoleService — repository mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.roles.exceptions import (
    RoleAlreadyExistsException,
    RoleInUseException,
    RoleNotFoundException,
    SystemRoleProtectedException,
)
from app.modules.roles.schemas import RoleCreateRequest, RoleUpdateRequest
from app.modules.roles.service import RoleService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return RoleService(mock_repo)


def test_create_raises_if_name_taken(service, mock_repo):
    mock_repo.get_by_name.return_value = MagicMock()
    with pytest.raises(RoleAlreadyExistsException):
        service.create_role(RoleCreateRequest(name="Teacher"), actor_id=uuid.uuid4())


def test_get_role_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(RoleNotFoundException):
        service.get_role(uuid.uuid4())


def test_delete_system_role_is_blocked(service, mock_repo):
    role_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=role_id, name="Super Admin")
    with pytest.raises(SystemRoleProtectedException):
        service.delete_role(role_id, actor_id=uuid.uuid4())
    mock_repo.soft_delete.assert_not_called()


def test_delete_role_in_use_is_blocked(service, mock_repo):
    role_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=role_id, name="Custom Moderator")
    mock_repo.count_users_with_role.return_value = 3
    with pytest.raises(RoleInUseException):
        service.delete_role(role_id, actor_id=uuid.uuid4())
    mock_repo.soft_delete.assert_not_called()


def test_delete_unused_custom_role_succeeds(service, mock_repo):
    role_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=role_id, name="Custom Moderator")
    mock_repo.count_users_with_role.return_value = 0
    service.delete_role(role_id, actor_id=uuid.uuid4())
    mock_repo.soft_delete.assert_called_once()
    mock_repo.commit.assert_called_once()


def test_cannot_deactivate_system_role_via_update(service, mock_repo):
    role_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=role_id, name="Admin")
    with pytest.raises(SystemRoleProtectedException):
        service.update_role(role_id, RoleUpdateRequest(status="inactive"), actor_id=uuid.uuid4())
    mock_repo.update.assert_not_called()


def test_can_update_description_of_system_role(service, mock_repo):
    role_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=role_id, name="Admin")
    service.update_role(role_id, RoleUpdateRequest(description="Updated desc"), actor_id=uuid.uuid4())
    mock_repo.update.assert_called_once()
