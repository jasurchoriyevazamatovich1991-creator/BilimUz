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


@pytest.fixture
def mock_group_repo():
    return MagicMock()


@pytest.fixture
def service_with_group_repo(mock_repo, mock_stats_repo, mock_attempt_repo, mock_answer_repo, mock_test_repo, mock_question_repo, mock_group_repo):
    """Sprint 80 — same 6-arg legacy construction as `service` above,
    plus the new optional question_group_repository wired in, exactly
    how get_result_service() constructs it for a real request."""
    return ResultService(
        mock_repo, mock_stats_repo, mock_attempt_repo, mock_answer_repo, mock_test_repo, mock_question_repo,
        question_group_repository=mock_group_repo,
    )


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
    """Sprint 69 (F1) — ResultService._update_statistics() now calls
    the single atomic StatisticsRepository.upsert_after_result() (real
    INSERT ... ON CONFLICT DO UPDATE against real PostgreSQL — see
    tests/integration/test_sprint69_statistics_null_subject_and_
    concurrency.py for the real-DB proof) instead of the old
    get()-then-create()-or-update() check-then-act pair. This mock-based
    unit test now asserts the new call shape/arguments; the underlying
    correct/wrong/tests_taken semantics this test protects are
    unchanged."""
    user_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="submitted", test_id=uuid.uuid4(), score=90, percentage=90)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_repo.get_by_attempt_id.return_value = None
    mock_test_repo.get_by_id.return_value = MagicMock(passing_score=None, subject_id=subject_id)
    mock_answer_repo.list_for_attempt.return_value = [MagicMock(is_correct=True), MagicMock(is_correct=False)]

    service.create_result(attempt.id, user_id)
    mock_stats_repo.upsert_after_result.assert_called_once_with(user_id, subject_id, 1, 1, 90.0)


def test_statistics_running_average_is_correct(service, mock_repo, mock_attempt_repo, mock_test_repo, mock_answer_repo, mock_stats_repo):
    """First result 80%, second 100% -> average must be 90%, not 100%.

    Sprint 69 (F1) — the running-average computation itself now
    happens DB-side inside StatisticsRepository.upsert_after_result()'s
    single atomic statement (see that method's docstring), not in
    Python here, so this mock-based unit test can only assert that
    ResultService forwards the correct raw inputs (percentage=100.0
    for this second result) to upsert_after_result() — the actual
    ((80*1)+100)/2 == 90.0 arithmetic is proven against real
    PostgreSQL by tests/integration/test_sprint69_statistics_null_
    subject_and_concurrency.py::test_f1_3_repeated_sequential_writes_
    do_not_duplicate (which exercises this exact two-result averaging
    scenario end-to-end)."""
    user_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="submitted", test_id=uuid.uuid4(), score=100, percentage=100)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_repo.get_by_attempt_id.return_value = None
    mock_test_repo.get_by_id.return_value = MagicMock(passing_score=None, subject_id=subject_id)
    mock_answer_repo.list_for_attempt.return_value = []

    service.create_result(attempt.id, user_id)
    mock_stats_repo.upsert_after_result.assert_called_once_with(user_id, subject_id, 0, 0, 100.0)


# --- Sprint 37: Result Analysis (get_result_detail) ---

def _make_question(qid, text="Savol?", qtype="single_choice", explanation=None, options=None, group_id=None):
    # Sprint 80 — group_id defaults to None explicitly (not left to
    # MagicMock's own auto-attribute, which would be a truthy MagicMock
    # object, not None) so get_result_detail()'s `question.group_id is
    # not None` checks behave correctly for every pre-Sprint-80 test
    # that doesn't care about grouping at all.
    q = MagicMock(id=qid, question_text=text, question_type=qtype, explanation=explanation, group_id=group_id)
    q.options = options or []
    return q


def _make_group(gid, title="Passage 1", stimulus_text="Once upon a time..."):
    return MagicMock(id=gid, title=title, stimulus_text=stimulus_text)


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
        MagicMock(question_id=q1, is_correct=True, selected_option=uuid.uuid4(), selected_options=None, text_answer=None),
        MagicMock(question_id=q2, is_correct=False, selected_option=uuid.uuid4(), selected_options=None, text_answer=None),
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
    mock_answer_repo.list_for_attempt.return_value = [MagicMock(question_id=q1, is_correct=None, selected_option=None, selected_options=None, text_answer=None)]
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
        MagicMock(question_id=q1, is_correct=True, selected_option=None, selected_options=[opt_a, opt_b], text_answer=None),
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
    mock_answer_repo.list_for_attempt.return_value = [MagicMock(question_id=q1, is_correct=True, selected_option=opt_a, selected_options=None, text_answer=None)]
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


# --- Sprint 70: Result Review Text Answer Visibility ---

def test_short_answer_text_answer_appears_in_question_review(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    """TEST 1 — a short_answer Answer.text_answer is exposed on the
    corresponding QuestionReviewOut."""
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1 = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=0, percentage=0, is_passed=None, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = [
        MagicMock(question_id=q1, is_correct=None, selected_option=None, selected_options=None, text_answer="Newton's second law"),
    ]
    mock_question_repo.list_by_ids.return_value = [_make_question(q1, qtype="short_answer")]

    detail = service.get_result_detail(result_id, user_id)
    review = detail.questions[0]
    assert review.text_answer == "Newton's second law"
    assert review.is_correct is None


def test_essay_text_answer_appears_in_question_review(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    """TEST 2 — same as above, for essay."""
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1 = uuid.uuid4()
    essay_text = "A long-form essay answer discussing the causes of..."
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=0, percentage=0, is_passed=None, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = [
        MagicMock(question_id=q1, is_correct=None, selected_option=None, selected_options=None, text_answer=essay_text),
    ]
    mock_question_repo.list_by_ids.return_value = [_make_question(q1, qtype="essay")]

    detail = service.get_result_detail(result_id, user_id)
    review = detail.questions[0]
    assert review.text_answer == essay_text
    assert review.is_correct is None


def test_question_with_no_answer_has_null_text_answer(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    """TEST 3 — no Answer row at all -> text_answer is null, same as
    every other per-question field."""
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1 = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=0, percentage=0, is_passed=None, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = []
    mock_question_repo.list_by_ids.return_value = [_make_question(q1, qtype="short_answer")]

    detail = service.get_result_detail(result_id, user_id)
    review = detail.questions[0]
    assert review.text_answer is None


def test_text_answer_does_not_alter_scoring_counts(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    """TEST 4 — exposing text_answer must not change the existing
    correct/incorrect/unanswered counting logic (still driven solely by
    Answer.is_correct, per Sprint 66's own exclusion of short_answer/
    essay from auto-grading)."""
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1, q2 = uuid.uuid4(), uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=1, percentage=50, is_passed=False, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1, q2], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = [
        MagicMock(question_id=q1, is_correct=True, selected_option=uuid.uuid4(), selected_options=None, text_answer=None),
        MagicMock(question_id=q2, is_correct=None, selected_option=None, selected_options=None, text_answer="an essay answer"),
    ]
    mock_question_repo.list_by_ids.return_value = [_make_question(q1), _make_question(q2, qtype="essay")]

    detail = service.get_result_detail(result_id, user_id)
    # q2 has a non-null text_answer but is_correct=None (never auto-graded)
    # -> still counted as unanswered, exactly as before Sprint 70.
    assert detail.correct_answers == 1
    assert detail.incorrect_answers == 0
    assert detail.unanswered == 1
    assert detail.questions[1].text_answer == "an essay answer"


def test_existing_choice_type_review_unchanged_by_text_answer_field(service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo):
    """TEST 5 — single_choice/multiple_choice/true_false answers keep
    their existing selected_option(s)/is_correct behavior; text_answer
    is simply null for these since Answer.text_answer is never populated
    for choice-based types (attempts/service.py's save_answer())."""
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1, q2, q3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    opt_a = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=2, percentage=67, is_passed=True, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1, q2, q3], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = [
        MagicMock(question_id=q1, is_correct=True, selected_option=opt_a, selected_options=None, text_answer=None),
        MagicMock(question_id=q2, is_correct=True, selected_option=None, selected_options=[opt_a], text_answer=None),
        MagicMock(question_id=q3, is_correct=False, selected_option=opt_a, selected_options=None, text_answer=None),
    ]
    mock_question_repo.list_by_ids.return_value = [
        _make_question(q1, qtype="single_choice"),
        _make_question(q2, qtype="multiple_choice"),
        _make_question(q3, qtype="true_false"),
    ]

    detail = service.get_result_detail(result_id, user_id)
    for review in detail.questions:
        assert review.text_answer is None
    assert detail.questions[0].selected_option == opt_a
    assert detail.questions[0].is_correct is True
    assert detail.questions[1].selected_options == [opt_a]
    assert detail.questions[2].is_correct is False


# --- Sprint 80: QuestionReviewOut group_id/group_title/stimulus_text ---
# Mirrors AttemptService._to_question_view()'s own Sprint 77 test
# coverage shape, through ResultService.get_result_detail() instead.

def test_grouped_question_includes_group_fields_when_group_repo_wired(
    service_with_group_repo, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo, mock_group_repo,
):
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1 = uuid.uuid4()
    group_id = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=1, percentage=100, is_passed=True, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = []
    mock_question_repo.list_by_ids.return_value = [_make_question(q1, text="Passage question 1", group_id=group_id)]
    mock_group_repo.list_active_by_ids.return_value = [_make_group(group_id, title="Passage 1", stimulus_text="Once upon a time...")]

    detail = service_with_group_repo.get_result_detail(result_id, user_id)
    review = detail.questions[0]
    assert review.group_id == group_id
    assert review.group_title == "Passage 1"
    assert review.stimulus_text == "Once upon a time..."
    # Single batched call, never one get_by_id() per question (N+1 avoidance).
    mock_group_repo.list_active_by_ids.assert_called_once_with([group_id])


def test_ungrouped_question_has_null_group_fields_even_with_group_repo_wired(
    service_with_group_repo, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo, mock_group_repo,
):
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1 = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=1, percentage=100, is_passed=True, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = []
    mock_question_repo.list_by_ids.return_value = [_make_question(q1, group_id=None)]

    detail = service_with_group_repo.get_result_detail(result_id, user_id)
    review = detail.questions[0]
    assert review.group_id is None
    assert review.group_title is None
    assert review.stimulus_text is None
    mock_group_repo.list_active_by_ids.assert_not_called()


def test_soft_deleted_group_renders_as_ungrouped(
    service_with_group_repo, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo, mock_group_repo,
):
    """A group soft-deleted after the question was authored must look
    exactly like 'never grouped' — list_active_by_ids() already excludes
    it, mirroring AttemptService's identical Sprint 77 guarantee."""
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1 = uuid.uuid4()
    group_id = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=1, percentage=100, is_passed=True, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = []
    mock_question_repo.list_by_ids.return_value = [_make_question(q1, group_id=group_id)]
    mock_group_repo.list_active_by_ids.return_value = []  # soft-deleted -> excluded

    detail = service_with_group_repo.get_result_detail(result_id, user_id)
    review = detail.questions[0]
    assert review.group_id is None
    assert review.group_title is None
    assert review.stimulus_text is None


def test_grouped_question_has_null_group_fields_when_group_repo_not_wired(
    service, mock_repo, mock_attempt_repo, mock_answer_repo, mock_question_repo,
):
    """Backward-compat — a legacy ResultService construction (no
    question_group_repository, exactly like the `service` fixture every
    pre-Sprint-80 test in this file uses) must degrade to all-None group
    fields even for a question that DOES have a group_id, never crash."""
    user_id = uuid.uuid4()
    result_id = uuid.uuid4()
    q1 = uuid.uuid4()
    group_id = uuid.uuid4()
    result = MagicMock(id=result_id, user_id=user_id, attempt_id=uuid.uuid4(), test_id=uuid.uuid4(), score=1, percentage=100, is_passed=True, status="final", created_at="2026-01-01")
    mock_repo.get_by_id.return_value = result
    attempt = MagicMock(id=result.attempt_id, question_order=[q1], start_time=None, finish_time=None)
    mock_attempt_repo.get_by_id.return_value = attempt
    mock_answer_repo.list_for_attempt.return_value = []
    mock_question_repo.list_by_ids.return_value = [_make_question(q1, group_id=group_id)]

    detail = service.get_result_detail(result_id, user_id)
    review = detail.questions[0]
    assert review.group_id is None
    assert review.group_title is None
    assert review.stimulus_text is None
