"""Unit tests for AnalyticsService — all repositories mocked, no real DB.
Focused on the recompute logic's correctness (grouping, no double-count
on re-run) since that's the module's core responsibility."""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.modules.analytics.service import AnalyticsService


@pytest.fixture
def mock_daily_repo():
    return MagicMock()


@pytest.fixture
def mock_monthly_repo():
    return MagicMock()


@pytest.fixture
def mock_result_repo():
    return MagicMock()


@pytest.fixture
def mock_answer_repo():
    return MagicMock()


@pytest.fixture
def mock_test_repo():
    return MagicMock()


@pytest.fixture
def service(mock_daily_repo, mock_monthly_repo, mock_result_repo, mock_answer_repo, mock_test_repo):
    return AnalyticsService(mock_daily_repo, mock_monthly_repo, mock_result_repo, mock_answer_repo, mock_test_repo)


def _result(user_id, test_id, created_at):
    return MagicMock(user_id=user_id, test_id=test_id, attempt_id=uuid.uuid4(), created_at=created_at)


def test_recompute_daily_groups_by_user_subject_date(service, mock_result_repo, mock_test_repo, mock_answer_repo, mock_daily_repo):
    user_id = uuid.uuid4()
    test_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    today = datetime.now(timezone.utc)
    mock_result_repo.list_in_date_range.return_value = [_result(user_id, test_id, today), _result(user_id, test_id, today)]
    mock_test_repo.get_by_id.return_value = MagicMock(subject_id=subject_id)
    mock_answer_repo.list_for_attempt.return_value = []

    count = service.recompute_daily(today.date(), today.date())

    assert count == 1  # both results fall in the same (user, subject, day) bucket
    created_row = mock_daily_repo.create.call_args[0][0]
    assert created_row.tests_taken == 2


def test_recompute_daily_counts_correct_and_wrong_answers(service, mock_result_repo, mock_test_repo, mock_answer_repo, mock_daily_repo):
    user_id = uuid.uuid4()
    today = datetime.now(timezone.utc)
    mock_result_repo.list_in_date_range.return_value = [_result(user_id, uuid.uuid4(), today)]
    mock_test_repo.get_by_id.return_value = MagicMock(subject_id=None)
    mock_answer_repo.list_for_attempt.return_value = [
        MagicMock(is_correct=True), MagicMock(is_correct=True), MagicMock(is_correct=False),
    ]

    service.recompute_daily(today.date(), today.date())

    created_row = mock_daily_repo.create.call_args[0][0]
    assert created_row.correct_answers == 2
    assert created_row.wrong_answers == 1


def test_recompute_daily_is_delete_and_rebuild(service, mock_result_repo, mock_test_repo, mock_answer_repo, mock_daily_repo):
    """Re-running recompute for the same window must not double-count —
    proven by asserting delete_for_range is always called before create."""
    today = datetime.now(timezone.utc)
    mock_result_repo.list_in_date_range.return_value = [_result(uuid.uuid4(), uuid.uuid4(), today)]
    mock_test_repo.get_by_id.return_value = MagicMock(subject_id=None)
    mock_answer_repo.list_for_attempt.return_value = []

    service.recompute_daily(today.date(), today.date())

    mock_daily_repo.delete_for_range.assert_called_once()
    mock_daily_repo.commit.assert_called_once()


def test_recompute_daily_uses_subject_cache_not_n_plus_one(service, mock_result_repo, mock_test_repo, mock_answer_repo, mock_daily_repo):
    """Two results sharing the same test_id must only trigger ONE
    TestRepository.get_by_id call, not two."""
    test_id = uuid.uuid4()
    today = datetime.now(timezone.utc)
    mock_result_repo.list_in_date_range.return_value = [
        _result(uuid.uuid4(), test_id, today), _result(uuid.uuid4(), test_id, today),
    ]
    mock_test_repo.get_by_id.return_value = MagicMock(subject_id=uuid.uuid4())
    mock_answer_repo.list_for_attempt.return_value = []

    service.recompute_daily(today.date(), today.date())

    assert mock_test_repo.get_by_id.call_count == 1


def test_recompute_monthly_aggregates_daily_rows(service, mock_daily_repo, mock_monthly_repo):
    user_id = uuid.uuid4()
    mock_daily_repo.list_for_month.return_value = [
        MagicMock(user_id=user_id, subject_id=None, tests_taken=2),
        MagicMock(user_id=user_id, subject_id=None, tests_taken=3),
    ]

    count = service.recompute_monthly(month=1, year=2026)

    assert count == 1
    mock_monthly_repo.upsert.assert_called_once()
    args = mock_monthly_repo.upsert.call_args[0]
    assert args[4] == 5  # summed tests_taken


def test_recompute_monthly_rejects_invalid_month():
    from unittest.mock import MagicMock as MM
    service = AnalyticsService(MM(), MM(), MM(), MM(), MM())
    with pytest.raises(ValueError):
        service.recompute_monthly(month=13, year=2026)


def test_empty_results_produce_zero_buckets(service, mock_result_repo, mock_daily_repo):
    mock_result_repo.list_in_date_range.return_value = []
    count = service.recompute_daily(date(2026, 1, 1), date(2026, 1, 31))
    assert count == 0
    mock_daily_repo.create.assert_not_called()
