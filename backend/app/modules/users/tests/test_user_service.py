"""Unit tests for UserService — repository mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import UserNotFoundException
from app.modules.users.exceptions import CannotModifySelfException
from app.modules.users.schemas import UserAdminUpdateRequest, UserSelfUpdateRequest
from app.modules.users.service import UserService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return UserService(mock_repo)


def test_get_user_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(UserNotFoundException):
        service.get_user(uuid.uuid4())


def test_update_own_profile_updates_only_provided_fields(service, mock_repo):
    user_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=user_id)
    service.update_own_profile(user_id, UserSelfUpdateRequest(first_name="Aziz"))

    called_updates = mock_repo.update.call_args[0][1]
    assert called_updates == {"first_name": "Aziz"}
    mock_repo.commit.assert_called_once()


def test_admin_cannot_update_self(service, mock_repo):
    actor_id = uuid.uuid4()
    with pytest.raises(CannotModifySelfException):
        service.admin_update_user(actor_id, UserAdminUpdateRequest(status="inactive"), actor_id=actor_id)
    mock_repo.update.assert_not_called()


def test_admin_update_logs_audit_action(service, mock_repo):
    target_id, actor_id = uuid.uuid4(), uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=target_id)
    service.admin_update_user(target_id, UserAdminUpdateRequest(status="inactive"), actor_id=actor_id)
    mock_repo.db.add.assert_called_once()  # log_action wrote an AuditLog row


def test_super_admin_cannot_change_own_role(service, mock_repo):
    actor_id = uuid.uuid4()
    with pytest.raises(CannotModifySelfException):
        service.change_role(actor_id, uuid.uuid4(), actor_id=actor_id)


def test_change_role_logs_old_and_new_role(service, mock_repo):
    target_id, actor_id, new_role = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=target_id, role_id=uuid.uuid4())
    service.change_role(target_id, new_role, actor_id=actor_id)
    mock_repo.update.assert_called_once()
    mock_repo.commit.assert_called_once()
