"""Unit tests for AIChatService — repositories and provider mocked."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.ai.exceptions import AIProviderNotConfiguredException, ChatNotFoundException
from app.modules.ai.providers import AIResponse
from app.modules.ai.service import AIChatService


@pytest.fixture
def mock_chat_repo():
    return MagicMock()


@pytest.fixture
def mock_history_repo():
    return MagicMock()


@pytest.fixture
def mock_provider():
    return MagicMock()


@pytest.fixture
def service(mock_chat_repo, mock_history_repo, mock_provider):
    return AIChatService(mock_chat_repo, mock_history_repo, mock_provider)


def test_get_chat_raises_when_not_owned(service, mock_chat_repo):
    mock_chat_repo.get_by_id.return_value = MagicMock(user_id=uuid.uuid4())
    with pytest.raises(ChatNotFoundException):
        service.get_chat(uuid.uuid4(), user_id=uuid.uuid4())


def test_start_chat_creates_and_commits(service, mock_chat_repo):
    service.start_chat(uuid.uuid4(), title="My chat")
    mock_chat_repo.create.assert_called_once()
    mock_chat_repo.commit.assert_called_once()


def test_send_message_propagates_provider_not_configured(service, mock_chat_repo, mock_history_repo, mock_provider):
    user_id = uuid.uuid4()
    chat_id = uuid.uuid4()
    mock_chat_repo.get_by_id.return_value = MagicMock(id=chat_id, user_id=user_id)
    mock_history_repo.list_recent_for_context.return_value = []
    mock_provider.generate.side_effect = AIProviderNotConfiguredException("not configured")

    with pytest.raises(AIProviderNotConfiguredException):
        service.send_message(chat_id, user_id, "Salom")


def test_send_message_logs_usage_even_when_provider_not_configured(service, mock_chat_repo, mock_history_repo, mock_provider):
    """Usage is logged on both success AND failure — a refused call is
    still usage-relevant (rate-limit/configuration signal)."""
    user_id = uuid.uuid4()
    chat_id = uuid.uuid4()
    mock_chat_repo.get_by_id.return_value = MagicMock(id=chat_id, user_id=user_id)
    mock_history_repo.list_recent_for_context.return_value = []
    mock_provider.generate.side_effect = AIProviderNotConfiguredException("not configured")

    with pytest.raises(AIProviderNotConfiguredException):
        service.send_message(chat_id, user_id, "Salom")

    mock_chat_repo.commit.assert_called_once()  # the usage-log commit still happened


def test_send_message_persists_user_message_before_calling_provider(service, mock_chat_repo, mock_history_repo, mock_provider):
    """Even if the provider call fails, the user's own message must
    already be saved — a user should never lose what they typed."""
    user_id = uuid.uuid4()
    chat_id = uuid.uuid4()
    mock_chat_repo.get_by_id.return_value = MagicMock(id=chat_id, user_id=user_id)
    mock_history_repo.list_recent_for_context.return_value = []
    mock_provider.generate.side_effect = AIProviderNotConfiguredException("not configured")

    with pytest.raises(AIProviderNotConfiguredException):
        service.send_message(chat_id, user_id, "Salom")

    mock_history_repo.create.assert_called_once()  # user message saved, assistant message never reached


def test_send_message_succeeds_and_saves_both_messages(service, mock_chat_repo, mock_history_repo, mock_provider):
    user_id = uuid.uuid4()
    chat_id = uuid.uuid4()
    mock_chat_repo.get_by_id.return_value = MagicMock(id=chat_id, user_id=user_id)
    mock_history_repo.list_recent_for_context.return_value = []
    mock_provider.generate.return_value = AIResponse(content="Salom, qalaysiz?", provider="test", tokens_used=10)

    user_msg, assistant_msg = service.send_message(chat_id, user_id, "Salom")

    assert mock_history_repo.create.call_count == 2
    mock_chat_repo.commit.assert_called_once()


def test_send_message_includes_prior_history_as_context(service, mock_chat_repo, mock_history_repo, mock_provider):
    user_id = uuid.uuid4()
    chat_id = uuid.uuid4()
    mock_chat_repo.get_by_id.return_value = MagicMock(id=chat_id, user_id=user_id)
    prior_entry = MagicMock(role="user", message="Oldingi savol")
    mock_history_repo.list_recent_for_context.return_value = [prior_entry]
    mock_provider.generate.return_value = AIResponse(content="Javob", provider="test")

    service.send_message(chat_id, user_id, "Yangi savol")

    sent_request = mock_provider.generate.call_args[0][0]
    assert len(sent_request.history) == 1
    assert sent_request.history[0].content == "Oldingi savol"
