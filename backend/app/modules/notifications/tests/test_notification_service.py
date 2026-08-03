"""Unit tests for NotificationService and TemplateService — repositories mocked."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.notifications.exceptions import NotificationNotFoundException, TemplateCodeAlreadyExistsException
from app.modules.notifications.service import NotificationService, TemplateService


def test_mark_read_raises_when_not_owned():
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = MagicMock(user_id=uuid.uuid4())
    service = NotificationService(mock_repo)
    with pytest.raises(NotificationNotFoundException):
        service.mark_read(uuid.uuid4(), user_id=uuid.uuid4())


def test_mark_read_succeeds_for_owner():
    mock_repo = MagicMock()
    user_id = uuid.uuid4()
    notification = MagicMock(user_id=user_id)
    mock_repo.get_by_id.return_value = notification
    service = NotificationService(mock_repo)
    service.mark_read(notification.id, user_id=user_id)
    mock_repo.mark_read.assert_called_once_with(notification)


def test_mark_all_read_returns_count():
    mock_repo = MagicMock()
    mock_repo.mark_all_read.return_value = 3
    service = NotificationService(mock_repo)
    count = service.mark_all_read(uuid.uuid4())
    assert count == 3


def test_create_notification_commits():
    mock_repo = MagicMock()
    service = NotificationService(mock_repo)
    service.create(uuid.uuid4(), "Title", "Message", "in_app", actor_id=uuid.uuid4())
    mock_repo.commit.assert_called_once()


def test_template_create_rejects_duplicate_code():
    mock_repo = MagicMock()
    mock_repo.get_by_code.return_value = MagicMock()
    service = TemplateService(mock_repo)
    with pytest.raises(TemplateCodeAlreadyExistsException):
        service.create("welcome_email", "email", "Welcome", "Hello!", actor_id=uuid.uuid4())


def test_template_create_succeeds_for_new_code():
    mock_repo = MagicMock()
    mock_repo.get_by_code.return_value = None
    service = TemplateService(mock_repo)
    template = service.create("welcome_email", "email", "Welcome", "Hello!", actor_id=uuid.uuid4())
    mock_repo.create.assert_called_once()
    assert template.code == "welcome_email"
