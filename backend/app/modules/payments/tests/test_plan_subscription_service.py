"""Unit tests for PlanService and SubscriptionService — repositories mocked."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.payments.exceptions import PlanNotFoundException
from app.modules.payments.schemas import PlanCreateRequest
from app.modules.payments.service import PlanService, SubscriptionService


def test_plan_create_commits():
    mock_repo = MagicMock()
    service = PlanService(mock_repo)
    service.create(PlanCreateRequest(name="Premium", price=50000, duration_days=30), actor_id=uuid.uuid4())
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()


def test_plan_get_raises_when_missing():
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = None
    service = PlanService(mock_repo)
    with pytest.raises(PlanNotFoundException):
        service.get(uuid.uuid4())


def test_subscribe_rejects_invalid_plan():
    mock_sub_repo = MagicMock()
    mock_plan_repo = MagicMock()
    mock_plan_repo.get_by_id.return_value = None
    service = SubscriptionService(mock_sub_repo, mock_plan_repo)
    with pytest.raises(PlanNotFoundException):
        service.subscribe(uuid.uuid4(), user_id=uuid.uuid4())


def test_subscribe_computes_end_date_from_plan_duration():
    mock_sub_repo = MagicMock()
    mock_plan_repo = MagicMock()
    mock_plan_repo.get_by_id.return_value = MagicMock(duration_days=30)
    service = SubscriptionService(mock_sub_repo, mock_plan_repo)

    subscription = service.subscribe(uuid.uuid4(), user_id=uuid.uuid4())

    delta = subscription.end_date - subscription.start_date
    assert delta.days == 30
    mock_sub_repo.commit.assert_called_once()
