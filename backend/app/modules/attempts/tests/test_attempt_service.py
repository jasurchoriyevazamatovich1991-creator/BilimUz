"""Unit tests for AttemptService — the core Test Engine logic. All five
repositories mocked, no real DB needed."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.modules.attempts.exceptions import (
    AttemptNotActiveException,
    AttemptNotFoundException,
    InvalidOptionReferenceException,
    InvalidQuestionReferenceException,
    MaxAttemptsExceededException,
    ResultNotAvailableException,
    TestNotPublishedException,
)
from app.modules.attempts.models import AttemptStatus
from app.modules.attempts.service import AttemptService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_answer_repo():
    return MagicMock()


@pytest.fixture
def mock_test_repo():
    return MagicMock()


@pytest.fixture
def mock_question_repo():
    return MagicMock()


@pytest.fixture
def mock_option_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_answer_repo, mock_test_repo, mock_question_repo, mock_option_repo):
    return AttemptService(mock_repo, mock_answer_repo, mock_test_repo, mock_question_repo, mock_option_repo)


# --- start_attempt -----------------------------------------------------

def test_start_rejects_unpublished_test(service, mock_test_repo):
    mock_test_repo.get_by_id.return_value = MagicMock(status="draft")
    with pytest.raises(TestNotPublishedException):
        service.start_attempt(uuid.uuid4(), user_id=uuid.uuid4())


def test_start_rejects_when_max_attempts_reached(service, mock_test_repo, mock_repo):
    mock_test_repo.get_by_id.return_value = MagicMock(status="published")
    mock_repo.count_for_user_and_test.return_value = 1  # DEFAULT_MAX_ATTEMPTS == 1
    with pytest.raises(MaxAttemptsExceededException):
        service.start_attempt(uuid.uuid4(), user_id=uuid.uuid4())


def test_start_succeeds_and_snapshots_question_order(service, mock_test_repo, mock_repo, mock_question_repo):
    mock_test_repo.get_by_id.return_value = MagicMock(status="published", duration=60, shuffle_questions=False)
    mock_repo.count_for_user_and_test.return_value = 0
    q_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    mock_question_repo.list_all_for_test.return_value = [MagicMock(id=qid) for qid in q_ids]

    attempt = service.start_attempt(uuid.uuid4(), user_id=uuid.uuid4())

    assert attempt.question_order == q_ids  # shuffle=False preserves order
    assert attempt.status == AttemptStatus.IN_PROGRESS
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()


# --- ownership / not-found ------------------------------------------------

def test_get_attempt_raises_for_wrong_owner(service, mock_repo):
    other_user_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(user_id=other_user_id, status="in_progress", expires_at=None)
    with pytest.raises(AttemptNotFoundException):
        service.get_attempt(uuid.uuid4(), user_id=uuid.uuid4())


def test_get_attempt_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(AttemptNotFoundException):
        service.get_attempt(uuid.uuid4(), user_id=uuid.uuid4())


# --- lazy auto-finish -----------------------------------------------------

def test_get_attempt_auto_finishes_when_expired(service, mock_repo, mock_answer_repo, mock_question_repo, mock_test_repo):
    user_id = uuid.uuid4()
    attempt = MagicMock(
        id=uuid.uuid4(), user_id=user_id, status="in_progress",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        question_order=[],
    )
    mock_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = []

    service.get_attempt(attempt.id, user_id=user_id)

    mock_repo.update.assert_called_once()
    called_updates = mock_repo.update.call_args[0][1]
    assert called_updates["status"] == "auto_finished"


def test_get_attempt_does_not_finish_when_not_expired(service, mock_repo):
    user_id = uuid.uuid4()
    attempt = MagicMock(
        user_id=user_id, status="in_progress",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    mock_repo.get_by_id.return_value = attempt
    service.get_attempt(attempt.id, user_id=user_id)
    mock_repo.update.assert_not_called()


# --- save_answer ------------------------------------------------------------

def test_save_answer_rejects_inactive_attempt(service, mock_repo):
    user_id = uuid.uuid4()
    attempt = MagicMock(user_id=user_id, status="submitted", expires_at=None)
    mock_repo.get_by_id.return_value = attempt
    with pytest.raises(AttemptNotActiveException):
        service.save_answer(attempt.id, user_id, uuid.uuid4(), uuid.uuid4())


def test_save_answer_rejects_question_not_in_attempt(service, mock_repo):
    user_id = uuid.uuid4()
    known_question = uuid.uuid4()
    attempt = MagicMock(user_id=user_id, status="in_progress", expires_at=None, question_order=[known_question])
    mock_repo.get_by_id.return_value = attempt
    with pytest.raises(InvalidQuestionReferenceException):
        service.save_answer(attempt.id, user_id, uuid.uuid4(), None)  # different question_id


def test_save_answer_rejects_option_from_wrong_question(service, mock_repo, mock_option_repo):
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    attempt = MagicMock(user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = attempt
    mock_option_repo.get_by_id.return_value = MagicMock(question_id=uuid.uuid4())  # mismatched
    with pytest.raises(InvalidOptionReferenceException):
        service.save_answer(attempt.id, user_id, question_id, uuid.uuid4())


def test_save_answer_succeeds_and_computes_correctness(service, mock_repo, mock_answer_repo, mock_option_repo):
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    option_id = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = attempt
    mock_option_repo.get_by_id.return_value = MagicMock(question_id=question_id, is_correct=True)
    mock_answer_repo.get.return_value = None

    service.save_answer(attempt.id, user_id, question_id, option_id)

    mock_answer_repo.create.assert_called_once()
    created_answer = mock_answer_repo.create.call_args[0][0]
    assert created_answer.is_correct is True
    mock_repo.commit.assert_called_once()


# --- submit / scoring -----------------------------------------------------

def test_submit_computes_score_correctly(service, mock_repo, mock_answer_repo, mock_question_repo, mock_test_repo):
    user_id = uuid.uuid4()
    q1, q2 = uuid.uuid4(), uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[q1, q2])
    mock_repo.get_by_id.return_value = attempt
    mock_question_repo.get_by_id.side_effect = lambda qid: MagicMock(id=qid, score=5)
    mock_answer_repo.list_for_attempt.return_value = [
        MagicMock(question_id=q1, is_correct=True),
        MagicMock(question_id=q2, is_correct=False),
    ]
    mock_test_repo.get_by_id.return_value = MagicMock(passing_score=None)

    result = service.submit_attempt(attempt.id, user_id)

    assert result.status == "submitted"
    mock_repo.commit.assert_called()


def test_submit_rejects_already_finished(service, mock_repo):
    user_id = uuid.uuid4()
    attempt = MagicMock(user_id=user_id, status="submitted", expires_at=None)
    mock_repo.get_by_id.return_value = attempt
    with pytest.raises(AttemptNotActiveException):
        service.submit_attempt(attempt.id, user_id)


def test_unanswered_questions_score_zero(service, mock_repo, mock_answer_repo, mock_question_repo, mock_test_repo):
    """An attempt with 2 questions (5 pts each) and only 1 answered
    correctly should score 5/10 = 50%, not 5/5 = 100%."""
    user_id = uuid.uuid4()
    q1, q2 = uuid.uuid4(), uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[q1, q2])
    mock_repo.get_by_id.return_value = attempt
    mock_question_repo.get_by_id.side_effect = lambda qid: MagicMock(id=qid, score=5)
    mock_answer_repo.list_for_attempt.return_value = [MagicMock(question_id=q1, is_correct=True)]  # q2 never answered
    mock_test_repo.get_by_id.return_value = MagicMock(passing_score=None)

    service.submit_attempt(attempt.id, user_id)

    called_updates = mock_repo.update.call_args[0][1]
    assert called_updates["percentage"] == 50.0


# --- result -------------------------------------------------------------

def test_result_unavailable_while_in_progress(service, mock_repo):
    user_id = uuid.uuid4()
    attempt = MagicMock(user_id=user_id, status="in_progress", expires_at=None)
    mock_repo.get_by_id.return_value = attempt
    with pytest.raises(ResultNotAvailableException):
        service.get_result(attempt.id, user_id)


def test_result_computes_is_passed_correctly(service, mock_repo, mock_answer_repo, mock_test_repo):
    user_id = uuid.uuid4()
    attempt = MagicMock(
        id=uuid.uuid4(), user_id=user_id, status="submitted", expires_at=None,
        score=80, percentage=80, question_order=[uuid.uuid4()],
    )
    mock_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = []
    mock_test_repo.get_by_id.return_value = MagicMock(passing_score=70)

    result = service.get_result(attempt.id, user_id)
    assert result.is_passed is True
