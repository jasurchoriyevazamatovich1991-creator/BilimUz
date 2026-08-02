"""Unit tests for ResultService — all repositories mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.results.exceptions import AttemptNotFinishedException, ResultNotFoundException
from app.modules.results.schemas import ResultListParams
from app.modules.results.service import ResultService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_stats_repo():
    return MagicMock()


@pytest.fixture
def mock_attempt_repo():
    return MagicMock()


@pytest.fixture
def mock_answer_repo():
    return MagicMock()


@pytest.fixture
def mock_test_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_stats_repo, mock_attempt_repo, mock_answer_repo, mock_test_repo):
    return ResultService(mock_repo, mock_stats_repo, mock_attempt_repo, mock_answer_repo, mock_test_repo)


def test_create_rejects_wrong_owner(service, mock_attempt_repo):
    other_user = uuid.uuid4()
    mock_attempt_repo.get_by_id.return_value = MagicMock(user_id=other_user, status="submitted")
    with pytest.raises(ResultNotFoundException):
        service.create_result(uuid.uuid4(), user_id=uuid.uuid4())


def test_create_rejects_unfinished_attempt(service, mock_attempt_repo):
    user_id = uuid.uuid4()
    mock_attempt_repo.get_by_id.return_value = MagicMock(user_id=user_id, status="in_progress")
    with pytest.raises(AttemptNotFinishedException):
        service.create_result(uuid.uuid4(), user_id=user_id)


def test_create_is_idempotent(service, mock_repo, mock_attempt_repo):
    user_id = uuid.uuid4()
    attempt_id = uuid.uuid4()
    mock_attempt_repo.get_by_id.return_value = MagicMock(user_id=user_id, status="submitted")
    existing = MagicMock()
    mock_repo.get_by_attempt_id.return_value = existing
    result = service.create_result(attempt_id, user_id)
    assert result is existing
    mock_repo.create.assert_not_called()


def test_create_snapshots_is_passed_true(service, mock_repo, mock_attempt_repo, mock_test_repo, mock_answer_repo):
    user_id = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="submitted", test_id=uuid.uuid4(), score=80, percentage=80)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_repo.get_by_attempt_id.return_value = None
    mock_test_repo.get_by_id.return_value = MagicMock(passing_score=70, subject_id=uuid.uuid4())
    mock_answer_repo.list_for_attempt.return_value = []

    result = service.create_result(attempt.id, user_id)
    assert result.is_passed is True


def test_create_is_passed_null_when_no_threshold(service, mock_repo, mock_attempt_repo, mock_test_repo, mock_answer_repo):
    user_id = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="submitted", test_id=uuid.uuid4(), score=80, percentage=80)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_repo.get_by_attempt_id.return_value = None
    mock_test_repo.get_by_id.return_value = MagicMock(passing_score=None, subject_id=None)
    mock_answer_repo.list_for_attempt.return_value = []

    result = service.create_result(attempt.id, user_id)
    assert result.is_passed is None


def test_get_result_raises_when_not_owned(service, mock_repo):
    mock_repo.get_by_id.return_value = MagicMock(user_id=uuid.uuid4())
    with pytest.raises(ResultNotFoundException):
        service.get_result(uuid.uuid4(), user_id=uuid.uuid4())


def test_statistics_created_on_first_result(service, mock_repo, mock_attempt_repo, mock_test_repo, mock_answer_repo, mock_stats_repo):
    user_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="submitted", test_id=uuid.uuid4(), score=90, percentage=90)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_repo.get_by_attempt_id.return_value = None
    mock_test_repo.get_by_id.return_value = MagicMock(passing_score=None, subject_id=subject_id)
    mock_answer_repo.list_for_attempt.return_value = [MagicMock(is_correct=True), MagicMock(is_correct=False)]
    mock_stats_repo.get_by_user_and_subject.return_value = None

    service.create_result(attempt.id, user_id)
    mock_stats_repo.create.assert_called_once()
    created_stats = mock_stats_repo.create.call_args[0][0]
    assert created_stats.tests_taken == 1
    assert created_stats.correct_answers == 1
    assert created_stats.wrong_answers == 1


def test_statistics_running_average_is_correct(service, mock_repo, mock_attempt_repo, mock_test_repo, mock_answer_repo, mock_stats_repo):
    """First result 80%, second 100% -> average must be 90%, not 100%."""
    user_id = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="submitted", test_id=uuid.uuid4(), score=100, percentage=100)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_repo.get_by_attempt_id.return_value = None
    mock_test_repo.get_by_id.return_value = MagicMock(passing_score=None, subject_id=uuid.uuid4())
    mock_answer_repo.list_for_attempt.return_value = []
    mock_stats_repo.get_by_user_and_subject.return_value = MagicMock(tests_taken=1, avg_score=80, correct_answers=0, wrong_answers=0)

    service.create_result(attempt.id, user_id)
    called_updates = mock_stats_repo.update.call_args[0][1]
    assert called_updates["avg_score"] == 90.0
