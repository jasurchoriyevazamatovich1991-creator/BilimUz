"""Unit tests for QueueService — the delivery engine. Repositories and
providers mocked. Focused on the fail-fast-on-unconfigured-provider
behavior and the MAX_ATTEMPTS bookkeeping."""
from unittest.mock import MagicMock

import pytest

from app.modules.notifications.exceptions import ProviderNotConfiguredException
from app.modules.notifications.service import QueueService


@pytest.fixture
def mock_email_repo():
    return MagicMock()


@pytest.fixture
def mock_sms_repo():
    return MagicMock()


@pytest.fixture
def mock_email_provider():
    return MagicMock()


@pytest.fixture
def mock_sms_provider():
    return MagicMock()


@pytest.fixture
def service(mock_email_repo, mock_sms_repo, mock_email_provider, mock_sms_provider):
    return QueueService(mock_email_repo, mock_sms_repo, mock_email_provider, mock_sms_provider)


def test_enqueue_email_always_succeeds_and_commits(service, mock_email_repo):
    service.enqueue_email("user@example.com", "Subject", "Body")
    mock_email_repo.enqueue.assert_called_once()
    mock_email_repo.commit.assert_called_once()


def test_enqueue_sms_always_succeeds_and_commits(service, mock_sms_repo):
    service.enqueue_sms("+998901234567", "Message")
    mock_sms_repo.enqueue.assert_called_once()
    mock_sms_repo.commit.assert_called_once()


def test_enqueue_is_not_deduplicated(service, mock_email_repo):
    """Unlike results/certificates' idempotent-create pattern, queueing
    the same email twice is valid (e.g. resending) — two calls, two rows."""
    service.enqueue_email("user@example.com", "Subject", "Body")
    service.enqueue_email("user@example.com", "Subject", "Body")
    assert mock_email_repo.enqueue.call_count == 2


def test_process_email_queue_propagates_provider_not_configured(service, mock_email_repo, mock_email_provider):
    """Fail-fast: the honest 'not configured' signal must reach the
    caller, not be silently swallowed into a 'processed: 0' response."""
    mock_email_repo.list_pending.return_value = [MagicMock()]
    mock_email_provider.send.side_effect = ProviderNotConfiguredException("no provider")
    with pytest.raises(ProviderNotConfiguredException):
        service.process_email_queue(batch_size=10)


def test_process_email_queue_with_no_pending_items_does_not_call_provider(service, mock_email_repo, mock_email_provider):
    mock_email_repo.list_pending.return_value = []
    result = service.process_email_queue(batch_size=10)
    assert result.processed == 0
    mock_email_provider.send.assert_not_called()


def test_process_email_queue_marks_transient_failures_without_stopping_batch(service, mock_email_repo, mock_email_provider):
    """A non-ProviderNotConfigured exception (e.g. a future real
    provider's transient network error) must not stop the whole batch —
    only ProviderNotConfiguredException fails fast."""
    items = [MagicMock(), MagicMock()]
    mock_email_repo.list_pending.return_value = items
    mock_email_provider.send.side_effect = [Exception("transient network error"), None]

    result = service.process_email_queue(batch_size=10)

    assert result.sent == 1
    assert result.failed == 1
    mock_email_repo.mark_attempt_failed.assert_called_once()
    mock_email_repo.mark_sent.assert_called_once()


def test_process_sms_queue_uses_sms_provider_not_email(service, mock_sms_repo, mock_sms_provider, mock_email_provider):
    mock_sms_repo.list_pending.return_value = [MagicMock(to_phone="+998901234567", message="hi")]
    service.process_sms_queue(batch_size=10)
    mock_sms_provider.send.assert_called_once()
    mock_email_provider.send.assert_not_called()
