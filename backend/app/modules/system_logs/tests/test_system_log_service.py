"""Unit tests for SystemLogService — repository mocked, no real DB needed."""
import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.modules.system_logs.exceptions import SystemLogNotFoundException
from app.modules.system_logs.schemas import SystemLogListParams
from app.modules.system_logs.service import SystemLogService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return SystemLogService(mock_repo)


def test_create_log_commits(service, mock_repo):
    log = service.create_log(level="error", message="Something failed", source="payments")
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()
    assert log.level == "error"
    assert log.source == "payments"


def test_create_log_accepts_context(service, mock_repo):
    service.create_log(level="warning", message="Slow query", context={"duration_ms": 4200})
    created_log = mock_repo.create.call_args[0][0]
    assert created_log.context == {"duration_ms": 4200}


def test_get_log_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(SystemLogNotFoundException):
        service.get_log(uuid.uuid4())


def test_get_log_returns_found_entry(service, mock_repo):
    log = MagicMock()
    mock_repo.get_by_id.return_value = log
    assert service.get_log(uuid.uuid4()) is log


def test_list_logs_rejects_oversized_date_range(service):
    with pytest.raises(ValueError):
        service.list_logs(SystemLogListParams(date_from=date(2026, 1, 1), date_to=date(2026, 6, 1)))


def test_list_logs_delegates_to_repository(service, mock_repo):
    mock_repo.list.return_value = ([], 0)
    items, total = service.list_logs(SystemLogListParams(level="error"))
    mock_repo.list.assert_called_once()
    assert items == []


def test_create_log_defaults_source_and_context_to_none(service, mock_repo):
    """A minimal call (level + message only) must not require source/context."""
    log = service.create_log(level="info", message="Startup complete")
    assert log.source is None
    assert log.context is None
