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


def _attempt(attempt_id, start_minutes_ago, duration_minutes):
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=start_minutes_ago)
    return MagicMock(id=attempt_id, start_time=start, finish_time=start + timedelta(minutes=duration_minutes))


def test_higher_score_ranks_first(service, mock_repo, mock_result_repo, mock_attempt_repo):
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    r1, r2 = _result(u1, 70), _result(u2, 90)
    mock_result_repo.list_for_subject.return_value = [r1, r2]
    # Sprint 73 — PERF-1: service now calls list_by_ids() once (batched),
    # not get_by_id() per user.
    mock_attempt_repo.list_by_ids.side_effect = lambda ids: [_attempt(aid, 10, 5) for aid in ids]

    service.recompute(subject_id=None, period="all_time")

    mock_attempt_repo.list_by_ids.assert_called_once()
    assert mock_attempt_repo.get_by_id.call_count == 0
    calls = mock_repo.upsert.call_args_list
    ranks = {c.args[0]: c.args[4] for c in calls}
    assert ranks[u2] == 1
    assert ranks[u1] == 2


def test_tiebreak_shorter_duration_wins_on_equal_score(service, mock_repo, mock_result_repo, mock_attempt_repo):
    u_fast, u_slow = uuid.uuid4(), uuid.uuid4()
    fast_attempt_id, slow_attempt_id = uuid.uuid4(), uuid.uuid4()
    mock_result_repo.list_for_subject.return_value = [
        MagicMock(user_id=u_fast, percentage=85, attempt_id=fast_attempt_id, created_at=datetime.now(timezone.utc)),
        MagicMock(user_id=u_slow, percentage=85, attempt_id=slow_attempt_id, created_at=datetime.now(timezone.utc)),
    ]
    attempts_by_id = {
        fast_attempt_id: _attempt(fast_attempt_id, 30, 5),
        slow_attempt_id: _attempt(slow_attempt_id, 30, 20),
    }
    mock_attempt_repo.list_by_ids.side_effect = lambda ids: [attempts_by_id[i] for i in ids]

    service.recompute(subject_id=None, period="all_time")

    mock_attempt_repo.list_by_ids.assert_called_once()
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
    mock_attempt_repo.list_by_ids.side_effect = lambda ids: [_attempt(aid, 10, 5) for aid in ids]

    ranked_count = service.recompute(subject_id=uuid.uuid4(), period="all_time")

    assert ranked_count == 1
    called_score = mock_repo.upsert.call_args_list[0].args[3]
    assert called_score == 95


def test_recompute_calls_commit(service, mock_repo, mock_result_repo, mock_attempt_repo):
    mock_result_repo.list_for_subject.return_value = [_result(uuid.uuid4(), 80)]
    mock_attempt_repo.list_by_ids.side_effect = lambda ids: [_attempt(aid, 10, 5) for aid in ids]
    service.recompute(subject_id=None, period="all_time")
    mock_repo.commit.assert_called_once()


def test_sort_with_tiebreak_batches_attempt_loading_not_per_row(service, mock_attempt_repo):
    """Sprint 73 — PERF-1 regression guard. Directly exercises
    _sort_with_tiebreak() with N users and asserts list_by_ids() is
    called exactly once (not N times), proving the N+1 is actually
    fixed and stays fixed."""
    users_and_attempts = [(uuid.uuid4(), uuid.uuid4()) for _ in range(5)]
    best_per_user = {
        user_id: MagicMock(user_id=user_id, percentage=float(70 + i), attempt_id=attempt_id)
        for i, (user_id, attempt_id) in enumerate(users_and_attempts)
    }
    attempts_by_id = {attempt_id: _attempt(attempt_id, 10, 5) for _, attempt_id in users_and_attempts}
    mock_attempt_repo.list_by_ids.side_effect = lambda ids: [attempts_by_id[i] for i in ids]

    result = service._sort_with_tiebreak(best_per_user)

    assert mock_attempt_repo.list_by_ids.call_count == 1
    assert mock_attempt_repo.get_by_id.call_count == 0
    assert len(result) == 5
    # Highest percentage (74) must rank first.
    assert result[0][1] == 74.0


def test_empty_results_produces_zero_ranked(service, mock_repo, mock_result_repo):
    mock_result_repo.list_for_subject.return_value = []
    ranked_count = service.recompute(subject_id=None, period="all_time")
    assert ranked_count == 0
