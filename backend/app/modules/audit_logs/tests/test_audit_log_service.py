"""Unit tests for AuditLogService — repository mocked, no real DB needed."""
import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.modules.audit_logs.exceptions import AuditLogNotFoundException
from app.modules.audit_logs.schemas import AuditLogListParams
from app.modules.audit_logs.service import AuditLogService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return AuditLogService(mock_repo)


def test_get_log_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(AuditLogNotFoundException):
        service.get_log(uuid.uuid4())


def test_get_log_returns_found_entry(service, mock_repo):
    log = MagicMock()
    mock_repo.get_by_id.return_value = log
    assert service.get_log(uuid.uuid4()) is log


def test_list_logs_delegates_to_repository(service, mock_repo):
    mock_repo.list.return_value = ([], 0)
    items, total = service.list_logs(AuditLogListParams())
    mock_repo.list.assert_called_once()
    assert items == []
    assert total == 0


def test_list_logs_rejects_oversized_date_range(service):
    with pytest.raises(ValueError):
        service.list_logs(AuditLogListParams(date_from=date(2026, 1, 1), date_to=date(2026, 6, 1)))


def test_list_logs_passes_filters_through_to_repository(service, mock_repo):
    mock_repo.list.return_value = ([], 0)
    user_id = uuid.uuid4()
    service.list_logs(AuditLogListParams(user_id=user_id, action="test.created"))
    called_params = mock_repo.list.call_args[0][0]
    assert called_params.user_id == user_id
    assert called_params.action == "test.created"
