"""Unit tests for PermissionService and RolePermissionService — repositories
mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.permissions.exceptions import (
    PermissionAlreadyExistsException,
    PermissionNotFoundException,
    RolePermissionAlreadyExistsException,
    RolePermissionNotFoundException,
)
from app.modules.permissions.schemas import PermissionCreateRequest
from app.modules.permissions.service import PermissionService, RolePermissionService


@pytest.fixture
def mock_perm_repo():
    return MagicMock()


@pytest.fixture
def permission_service(mock_perm_repo):
    return PermissionService(mock_perm_repo)


@pytest.fixture
def mock_rp_repo():
    return MagicMock()


@pytest.fixture
def role_permission_service(mock_rp_repo, mock_perm_repo):
    return RolePermissionService(mock_rp_repo, mock_perm_repo)


def test_create_permission_raises_if_code_taken(permission_service, mock_perm_repo):
    mock_perm_repo.get_by_code.return_value = MagicMock()
    with pytest.raises(PermissionAlreadyExistsException):
        permission_service.create_permission(
            PermissionCreateRequest(name="Create Test", code="CREATE_TEST", module="tests"),
            actor_id=uuid.uuid4(),
        )


def test_get_permission_raises_when_missing(permission_service, mock_perm_repo):
    mock_perm_repo.get_by_id.return_value = None
    with pytest.raises(PermissionNotFoundException):
        permission_service.get_permission(uuid.uuid4())


def test_assign_raises_if_permission_missing(role_permission_service, mock_perm_repo):
    mock_perm_repo.get_by_id.return_value = None
    with pytest.raises(PermissionNotFoundException):
        role_permission_service.assign(uuid.uuid4(), uuid.uuid4(), actor_id=uuid.uuid4())


def test_assign_raises_if_already_granted(role_permission_service, mock_perm_repo, mock_rp_repo):
    mock_perm_repo.get_by_id.return_value = MagicMock()
    mock_rp_repo.get.return_value = MagicMock()
    with pytest.raises(RolePermissionAlreadyExistsException):
        role_permission_service.assign(uuid.uuid4(), uuid.uuid4(), actor_id=uuid.uuid4())


def test_assign_succeeds_and_commits(role_permission_service, mock_perm_repo, mock_rp_repo):
    mock_perm_repo.get_by_id.return_value = MagicMock()
    mock_rp_repo.get.return_value = None
    role_permission_service.assign(uuid.uuid4(), uuid.uuid4(), actor_id=uuid.uuid4())
    mock_rp_repo.create.assert_called_once()
    mock_rp_repo.commit.assert_called_once()


def test_revoke_raises_if_grant_not_found(role_permission_service, mock_rp_repo):
    mock_rp_repo.get.return_value = None
    with pytest.raises(RolePermissionNotFoundException):
        role_permission_service.revoke(uuid.uuid4(), uuid.uuid4(), actor_id=uuid.uuid4())


def test_role_has_permission_delegates_to_repository(role_permission_service, mock_rp_repo):
    mock_rp_repo.role_has_permission_code.return_value = True
    role_id = uuid.uuid4()
    assert role_permission_service.role_has_permission(role_id, "CREATE_TEST") is True
    mock_rp_repo.role_has_permission_code.assert_called_once_with(role_id, "CREATE_TEST")
