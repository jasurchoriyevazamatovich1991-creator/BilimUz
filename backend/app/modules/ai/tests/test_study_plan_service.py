"""Unit tests for StudyPlanService — repository mocked."""
import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.modules.ai.exceptions import StudyPlanNotFoundException
from app.modules.ai.schemas import StudyPlanCreateRequest
from app.modules.ai.service import StudyPlanService


def test_create_commits_and_returns_plan():
    mock_repo = MagicMock()
    service = StudyPlanService(mock_repo)
    data = StudyPlanCreateRequest(plan={"weeks": []}, start_date=date(2026, 1, 1), end_date=date(2026, 6, 1))
    plan = service.create(data, user_id=uuid.uuid4())
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()


def test_get_raises_when_not_owned():
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = MagicMock(user_id=uuid.uuid4())
    service = StudyPlanService(mock_repo)
    with pytest.raises(StudyPlanNotFoundException):
        service.get(uuid.uuid4(), user_id=uuid.uuid4())


def test_schema_rejects_invalid_date_range():
    with pytest.raises(ValueError):
        StudyPlanCreateRequest(plan={}, start_date=date(2026, 6, 1), end_date=date(2026, 1, 1))
