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
def mock_question_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_stats_repo, mock_attempt_repo, mock_answer_repo, mock_test_repo, mock_question_repo):
    return ResultService(mock_repo, mock_stats_repo, mock_attempt_repo, mock_answer_repo, mock_test_repo, mock_question_repo)


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


# --- Sprint 37: Result Analysis (get_result_detail) ---

def _make_question(qid, text="Savol?", qtype="single_choice", explanation=None, options=None):
    q = MagicMock(id=qid, question_text=text, question_type=qtype, explanation=explanation)
    q.options = options or []
    return q


def _make_option(oid, text, is_correct):
    return MagicMock(id=oid, option_text=text, is_correct=is_correct)


def test_result_detail_contains_all_analysis_fields(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1 = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=5, percentage=100, is_passed=True, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = []
    mock_question_repo.list_by_ids.return_value = [_make_question(q1)]

    detail = service.get_result_detail(result_id, user_id)

    assert detail.total_questions == 1
    assert hasattr(detail, "correct_answers")
    assert hasattr(detail, "incorrect_answers")
    assert hasattr(detail, "unanswered")
    assert hasattr(detail, "questions")


def test_correct_incorrect_unanswered_counts(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1, q2, q3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=1, percentage=33, is_passed=False, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1, q2, q3], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = [
        MagicMock(question_id=q1, is_correct=True, selected_option=uuid.uuid4(), selected_options=None),
        MagicMock(question_id=q2, is_correct=False, selected_option=uuid.uuid4(), selected_options=None),
        # q3 has no Answer row at all -> unanswered
    ]
    mock_question_repo.list_by_ids.return_value = [_make_question(q1), _make_question(q2), _make_question(q3)]

    detail = service.get_result_detail(result_id, user_id)

    assert detail.correct_answers == 1
    assert detail.incorrect_answers == 1
    assert detail.unanswered == 1
    assert detail.total_questions == 3


def test_unanswered_via_null_is_correct_also_counts_as_unanswered(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    """An Answer row CAN exist with is_correct=None (empty selection,
    per attempts/service.py's own None-for-unanswered convention) — this
    must also count as unanswered, not silently miscounted."""
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1 = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=0, percentage=0, is_passed=False, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = [MagicMock(question_id=q1, is_correct=None, selected_option=None, selected_options=None)]
    mock_question_repo.list_by_ids.return_value = [_make_question(q1)]

    detail = service.get_result_detail(result_id, user_id)
    assert detail.unanswered == 1
    assert detail.correct_answers == 0
    assert detail.incorrect_answers == 0


def test_time_spent_calculated_from_real_timestamps(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    from datetime import datetime, timedelta, timezone
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    start = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    finish = start + timedelta(minutes=12, seconds=34)
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=1, percentage=100, is_passed=True, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[], start_time=start, finish_time=finish)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = []
    mock_question_repo.list_by_ids.return_value = []

    detail = service.get_result_detail(result_id, user_id)
    assert detail.time_spent_seconds == 754  # 12*60 + 34


def test_time_spent_is_none_when_finish_time_missing(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    """Historical/edge-case data safety — never fabricate a time value."""
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=0, percentage=0, is_passed=None, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = []
    mock_question_repo.list_by_ids.return_value = []

    detail = service.get_result_detail(result_id, user_id)
    assert detail.time_spent_seconds is None


def test_multiple_choice_answer_shows_selected_options_array(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    """Sprint 30 compatibility — multiple_choice answers use
    selected_options (plural), not selected_option."""
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1 = uuid.uuid4()
    opt_a, opt_b = uuid.uuid4(), uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=1, percentage=100, is_passed=True, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = [
        MagicMock(question_id=q1, is_correct=True, selected_option=None, selected_options=[opt_a, opt_b]),
    ]
    mock_question_repo.list_by_ids.return_value = [_make_question(
        q1, qtype="multiple_choice",
        options=[_make_option(opt_a, "A", True), _make_option(opt_b, "B", True)],
    )]

    detail = service.get_result_detail(result_id, user_id)
    review = detail.questions[0]
    assert review.selected_options == [opt_a, opt_b]
    assert review.selected_option is None
    assert review.is_correct is True


def test_question_review_includes_text_options_and_explanation(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1 = uuid.uuid4()
    opt_a = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=1, percentage=100, is_passed=True, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = [MagicMock(question_id=q1, is_correct=True, selected_option=opt_a, selected_options=None)]
    mock_question_repo.list_by_ids.return_value = [_make_question(
        q1, text="2+2 nechi?", explanation="Oddiy qo'shish", options=[_make_option(opt_a, "4", True)],
    )]

    detail = service.get_result_detail(result_id, user_id)
    review = detail.questions[0]
    assert review.question_text == "2+2 nechi?"
    assert review.explanation == "Oddiy qo'shish"
    assert review.options[0].option_text == "4"
    assert review.options[0].is_correct is True


def test_another_student_cannot_inspect_the_result(service, mock_repo, mock_attempt_repo):
    """Reuses get_result()'s exact ownership check — a result owned by
    a DIFFERENT user must raise, never leak into get_result_detail()."""
    owner_id = uuid.uuid4()
    intruder_id = uuid.uuid4()
    result = MagicMock(id=uuid.uuid4(), user_id=owner_id)
    mock_repo.get_by_id.return_value = result

    with pytest.raises(ResultNotFoundException):
        service.get_result_detail(result.id, intruder_id)
    mock_attempt_repo.get_by_id.assert_not_called()  # never even reaches attempt/answer lookups


def test_existing_result_fields_remain_present_and_compatible(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    """ResultDetailOut extends ResultOut — every original field
    (id/attempt_id/user_id/test_id/score/percentage/is_passed/status/
    created_at) must still be present and correctly populated."""
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    attempt_id = uuid.uuid4()
    test_id = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=attempt_id, test_id=test_id, score=7.5, percentage=75.0, is_passed=True, status="final", created_at="2026-01-01T00:00:00")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=attempt_id, question_order=[], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = []
    mock_question_repo.list_by_ids.return_value = []

    detail = service.get_result_detail(result_id, user_id)
    assert detail.id == result_id
    assert detail.attempt_id == attempt_id
    assert detail.user_id == user_id
    assert detail.test_id == test_id
    assert detail.score == 7.5
    assert detail.percentage == 75.0
    assert detail.is_passed is True
    assert detail.status == "final"
