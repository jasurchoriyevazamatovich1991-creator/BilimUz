"""Unit tests for PaymentService — the module's most important tests are
the webhook idempotency ones (both the service-layer check AND the
DB-constraint race-condition fallback)."""
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.payments.exceptions import (
    PaymentAlreadyRefundedException,
    PaymentNotFoundException,
    PaymentNotRefundableException,
    PaymentProviderNotConfiguredException,
)
from app.modules.payments.providers import PaymentProviderRegistry, UnconfiguredPaymentProvider, WebhookVerificationResult
from app.modules.payments.schemas import InitiatePaymentRequest
from app.modules.payments.service import PaymentService


@pytest.fixture
def mock_payment_repo():
    return MagicMock()


@pytest.fixture
def mock_txn_repo():
    return MagicMock()


@pytest.fixture
def unconfigured_registry():
    return PaymentProviderRegistry({"click": UnconfiguredPaymentProvider()})


@pytest.fixture
def service(mock_payment_repo, mock_txn_repo, unconfigured_registry):
    return PaymentService(mock_payment_repo, mock_txn_repo, unconfigured_registry)


def test_initiate_creates_pending_payment_before_calling_provider(service, mock_payment_repo):
    """Even though the provider raises (unconfigured), the payment row
    must already exist — an audit trail of the attempt, not lost."""
    data = InitiatePaymentRequest(amount=50000, provider="click")
    with pytest.raises(PaymentProviderNotConfiguredException):
        service.initiate(data, user_id=uuid.uuid4())
    mock_payment_repo.create.assert_called_once()
    mock_payment_repo.commit.assert_called_once()


def test_webhook_raises_when_provider_not_configured(service):
    with pytest.raises(PaymentProviderNotConfiguredException):
        service.handle_webhook("click", b"{}", {})


def test_webhook_idempotency_returns_existing_without_reprocessing(service, mock_txn_repo, unconfigured_registry):
    """THE critical test: a duplicate provider_txn_id must not create a
    second transaction or re-update the payment status."""
    existing_txn = MagicMock()
    mock_txn_repo.get_by_provider_txn_id.return_value = existing_txn

    # bypass the unconfigured provider by injecting a fake verified provider
    fake_provider = MagicMock()
    fake_provider.verify_webhook.return_value = WebhookVerificationResult(
        payment_id=str(uuid.uuid4()), provider_txn_id="txn-123", is_success=True, raw_payload={},
    )
    registry = PaymentProviderRegistry({"click": fake_provider})
    svc = PaymentService(MagicMock(), mock_txn_repo, registry)

    result = svc.handle_webhook("click", b"{}", {})

    assert result is existing_txn
    mock_txn_repo.create.assert_not_called()


def test_webhook_race_condition_handled_via_integrity_error(mock_txn_repo):
    """Two 'concurrent' deliveries: the first passes the check-then-insert
    (no existing row found), but the DB-level UNIQUE constraint (migration
    0003) rejects the insert — simulated here via IntegrityError. The
    service must recover by returning the winning transaction, not crash."""
    payment_id = uuid.uuid4()
    mock_payment_repo = MagicMock()
    mock_payment_repo.get_by_id.return_value = MagicMock(id=payment_id)

    mock_txn_repo.get_by_provider_txn_id.side_effect = [None, MagicMock()]  # not found, then found after rollback
    mock_txn_repo.create.side_effect = IntegrityError("stmt", "params", Exception("duplicate key"))

    fake_provider = MagicMock()
    fake_provider.verify_webhook.return_value = WebhookVerificationResult(
        payment_id=str(payment_id), provider_txn_id="txn-race", is_success=True, raw_payload={},
    )
    registry = PaymentProviderRegistry({"click": fake_provider})
    svc = PaymentService(mock_payment_repo, mock_txn_repo, registry)

    result = svc.handle_webhook("click", b"{}", {})

    mock_txn_repo.db.rollback.assert_called_once()
    assert result is not None


def test_webhook_rejects_unknown_payment_id(mock_txn_repo):
    mock_payment_repo = MagicMock()
    mock_payment_repo.get_by_id.return_value = None
    mock_txn_repo.get_by_provider_txn_id.return_value = None

    fake_provider = MagicMock()
    fake_provider.verify_webhook.return_value = WebhookVerificationResult(
        payment_id=str(uuid.uuid4()), provider_txn_id="txn-999", is_success=True, raw_payload={},
    )
    registry = PaymentProviderRegistry({"click": fake_provider})
    svc = PaymentService(mock_payment_repo, mock_txn_repo, registry)

    with pytest.raises(PaymentNotFoundException):
        svc.handle_webhook("click", b"{}", {})


def test_refund_rejects_already_refunded(service, mock_payment_repo):
    mock_payment_repo.get_by_id.return_value = MagicMock(status="refunded")
    with pytest.raises(PaymentAlreadyRefundedException):
        service.refund(uuid.uuid4(), actor_id=uuid.uuid4())


def test_refund_rejects_non_success_payment(service, mock_payment_repo):
    mock_payment_repo.get_by_id.return_value = MagicMock(status="pending")
    with pytest.raises(PaymentNotRefundableException):
        service.refund(uuid.uuid4(), actor_id=uuid.uuid4())


def test_refund_raises_when_provider_not_configured(service, mock_payment_repo, mock_txn_repo):
    mock_payment_repo.get_by_id.return_value = MagicMock(status="success", provider="click", id=uuid.uuid4())
    mock_txn_repo.list_for_payment.return_value = []
    with pytest.raises(PaymentProviderNotConfiguredException):
        service.refund(uuid.uuid4(), actor_id=uuid.uuid4())


def test_get_raises_when_not_owned(service, mock_payment_repo):
    mock_payment_repo.get_by_id.return_value = MagicMock(user_id=uuid.uuid4())
    with pytest.raises(PaymentNotFoundException):
        service.get(uuid.uuid4(), user_id=uuid.uuid4())
