"""Unit tests for RankingService — the calculation engine. Focused
heavily on the approved 3-level tie-break rule."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.modules.results.service import RankingService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_result_repo():
    return MagicMock()


@pytest.fixture
def mock_attempt_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_result_repo, mock_attempt_repo):
    return RankingService(mock_repo, mock_result_repo, mock_attempt_repo)


def _result(user_id, percentage, attempt_id=None):
    return MagicMock(user_id=user_id, percentage=percentage, attempt_id=attempt_id or uuid.uuid4(), created_at=datetime.now(timezone.utc))


def _attempt(start_minutes_ago, duration_minutes):
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=start_minutes_ago)
    return MagicMock(start_time=start, finish_time=start + timedelta(minutes=duration_minutes))


def test_higher_score_ranks_first(service, mock_repo, mock_result_repo, mock_attempt_repo):
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    mock_result_repo.list_for_subject.return_value = [_result(u1, 70), _result(u2, 90)]
    mock_attempt_repo.get_by_id.return_value = _attempt(10, 5)

    service.recompute(subject_id=None, period="all_time")

    calls = mock_repo.upsert.call_args_list
    ranks = {c.args[0]: c.args[4] for c in calls}
    assert ranks[u2] == 1
    assert ranks[u1] == 2


def test_tiebreak_shorter_duration_wins_on_equal_score(service, mock_repo, mock_result_repo, mock_attempt_repo):
    u_fast, u_slow = uuid.uuid4(), uuid.uuid4()
    mock_result_repo.list_for_subject.return_value = [
        MagicMock(user_id=u_fast, percentage=85, attempt_id=uuid.uuid4(), created_at=datetime.now(timezone.utc)),
        MagicMock(user_id=u_slow, percentage=85, attempt_id=uuid.uuid4(), created_at=datetime.now(timezone.utc)),
    ]

    def attempt_for(attempt_id):
        # first call = u_fast's attempt (5 min), second = u_slow's (20 min)
        return _attempt(30, 5) if attempt_for.calls == 0 else _attempt(30, 20)
    attempt_for.calls = 0

    def side_effect(attempt_id):
        attempt_for.calls += 1
        return _attempt(30, 5) if attempt_for.calls == 1 else _attempt(30, 20)

    mock_attempt_repo.get_by_id.side_effect = side_effect

    service.recompute(subject_id=None, period="all_time")

    calls = mock_repo.upsert.call_args_list
    ranks = {c.args[0]: c.args[4] for c in calls}
    assert ranks[u_fast] == 1
    assert ranks[u_slow] == 2


def test_only_best_result_per_user_counts(service, mock_repo, mock_result_repo, mock_attempt_repo):
    """A user with two results (different tests, same subject) should be
    ranked once, using their BEST percentage."""
    user_id = uuid.uuid4()
    mock_result_repo.list_for_subject.return_value = [
        _result(user_id, 60), _result(user_id, 95),
    ]
    mock_attempt_repo.get_by_id.return_value = _attempt(10, 5)

    ranked_count = service.recompute(subject_id=uuid.uuid4(), period="all_time")

    assert ranked_count == 1
    called_score = mock_repo.upsert.call_args_list[0].args[3]
    assert called_score == 95


def test_recompute_calls_commit(service, mock_repo, mock_result_repo, mock_attempt_repo):
    mock_result_repo.list_for_subject.return_value = [_result(uuid.uuid4(), 80)]
    mock_attempt_repo.get_by_id.return_value = _attempt(10, 5)
    service.recompute(subject_id=None, period="all_time")
    mock_repo.commit.assert_called_once()


def test_empty_results_produces_zero_ranked(service, mock_repo, mock_result_repo):
    mock_result_repo.list_for_subject.return_value = []
    ranked_count = service.recompute(subject_id=None, period="all_time")
    assert ranked_count == 0
