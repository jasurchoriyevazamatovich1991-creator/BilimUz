"""Unit tests for the four settings services — repositories mocked."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.settings.exceptions import SettingNotFoundException
from app.modules.settings.service import AiSettingsService, GeneralSettingsService, PaymentSettingsService, SmtpSettingsService


def test_general_get_raises_when_missing():
    mock_repo = MagicMock()
    mock_repo.get_by_key.return_value = None
    service = GeneralSettingsService(mock_repo)
    with pytest.raises(SettingNotFoundException):
        service.get("site_name")


def test_general_upsert_commits(mock_repo=None):
    mock_repo = MagicMock()
    service = GeneralSettingsService(mock_repo)
    service.upsert("site_name", {"value": "BilimUz"}, actor_id=uuid.uuid4())
    mock_repo.commit.assert_called_once()


def test_smtp_upsert_passes_plaintext_password_to_repository():
    """The service must NOT encrypt directly — that's the repository's
    job (which delegates to EncryptionService). This test confirms the
    service passes plaintext through unchanged, trusting the repo layer."""
    mock_repo = MagicMock()
    service = SmtpSettingsService(mock_repo)
    service.upsert("smtp.example.com", 587, "user", "plaintext-pass", "noreply@bilimuz.uz", actor_id=uuid.uuid4())
    call_args = mock_repo.upsert.call_args[0]
    assert "plaintext-pass" in call_args


def test_payment_get_raises_when_missing():
    mock_repo = MagicMock()
    mock_repo.get_by_provider.return_value = None
    service = PaymentSettingsService(mock_repo)
    with pytest.raises(SettingNotFoundException):
        service.get("click")


def test_ai_upsert_commits():
    mock_repo = MagicMock()
    service = AiSettingsService(mock_repo)
    service.upsert("openai", "sk-test123", "gpt-4", actor_id=uuid.uuid4())
    mock_repo.commit.assert_called_once()
