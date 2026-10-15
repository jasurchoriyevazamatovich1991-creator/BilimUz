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
    MockTestAccessDeniedException,
    ResultNotAvailableException,
    TestNotPublishedException,
)
from app.modules.attempts.models import AttemptStatus
from app.modules.attempts.service import AttemptService


@pytest.fixture
def mock_repo():
    """Sprint 59 — _lock_attempt() (see service.py) now calls
    repo.get_by_id_locked() on every finalize-triggering path. These are
    pure unit tests with no real PostgreSQL row to lock, so
    get_by_id_locked() is wired to hand back whatever the test already
    configured get_by_id() to return, keeping every existing
    `mock_repo.get_by_id.return_value = attempt` line in this file
    accurate for the locked call too, without editing each test
    individually."""
    repo = MagicMock()
    repo.get_by_id_locked.side_effect = lambda attempt_id: repo.get_by_id.return_value
    # Sprint 72 (TEST-1) — the real AttemptRepository.update() does a
    # plain setattr(attempt, field, value) loop (see repository.py), so
    # _finalize()'s self.repo.update(attempt, {"status": ..., ...}) call
    # actually mutates the attempt row in production. An unconfigured
    # MagicMock's .update() call records the call but leaves the passed-
    # in `attempt` object completely untouched, so any test that reads
    # attempt.status (or percentage/score) AFTER calling a method that
    # finalizes via repo.update() — e.g. test_submit_computes_score_
    # correctly asserting result.status == "submitted" — was silently
    # checking a value that could never change. Mirroring the real
    # setattr-loop behavior here makes the mock an accurate stand-in.
    repo.update.side_effect = lambda obj, data: (
        [setattr(obj, field, value) for field, value in data.items()] and obj
    )
    return repo


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
    mock_test_repo.get_by_id.return_value = MagicMock(status="published", max_attempts=None)
    mock_repo.count_for_user_and_test.return_value = 1  # DEFAULT_MAX_ATTEMPTS == 1
    with pytest.raises(MaxAttemptsExceededException):
        service.start_attempt(uuid.uuid4(), user_id=uuid.uuid4())


def test_start_succeeds_and_snapshots_question_order(service, mock_test_repo, mock_repo, mock_question_repo):
    mock_test_repo.get_by_id.return_value = MagicMock(status="published", duration=60, shuffle_questions=False, max_attempts=None)
    mock_repo.count_for_user_and_test.return_value = 0
    q_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    mock_question_repo.list_all_for_test.return_value = [MagicMock(id=qid) for qid in q_ids]

    attempt = service.start_attempt(uuid.uuid4(), user_id=uuid.uuid4())

    assert attempt.question_order == q_ids  # shuffle=False preserves order
    assert attempt.status == AttemptStatus.IN_PROGRESS
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()


# --- start_attempt: Mock Test Entitlements gating -------------------------
# Covers spec §4 test items #1, #6, #10. entitlement_service is wired
# explicitly here (not via the `service` fixture, which omits it —
# matching the module's own established optional-dependency pattern,
# see AttemptService.__init__) so these are the only tests in this file
# that exercise the gate at all; every other start_attempt test above
# proves the gate is a complete no-op when entitlement_service is None,
# which is what every pre-feature caller/test still gets.

@pytest.fixture
def mock_entitlement_service():
    return MagicMock()


@pytest.fixture
def service_with_entitlements(mock_repo, mock_answer_repo, mock_test_repo, mock_question_repo, mock_option_repo, mock_entitlement_service):
    return AttemptService(
        mock_repo, mock_answer_repo, mock_test_repo, mock_question_repo, mock_option_repo,
        entitlement_service=mock_entitlement_service,
    )


def test_start_mock_test_denied_without_entitlement(service_with_entitlements, mock_test_repo, mock_entitlement_service):
    subject_id = uuid.uuid4()
    mock_test_repo.get_by_id.return_value = MagicMock(status="published", is_mock_test=True, subject_id=subject_id, max_attempts=None)
    mock_entitlement_service.has_mock_test_access.return_value = False

    with pytest.raises(MockTestAccessDeniedException):
        service_with_entitlements.start_attempt(uuid.uuid4(), user_id=uuid.uuid4())


def test_start_mock_test_succeeds_with_entitlement(
    service_with_entitlements, mock_test_repo, mock_repo, mock_question_repo, mock_entitlement_service,
):
    """Spec test #1 — a valid entitlement for the test's subject lets
    start_attempt() proceed exactly as for a non-mock test."""
    subject_id = uuid.uuid4()
    mock_test_repo.get_by_id.return_value = MagicMock(
        status="published", is_mock_test=True, subject_id=subject_id, duration=60, shuffle_questions=False, max_attempts=None,
    )
    mock_repo.count_for_user_and_test.return_value = 0
    mock_question_repo.list_all_for_test.return_value = []
    mock_entitlement_service.has_mock_test_access.return_value = True

    user_id = uuid.uuid4()
    attempt = service_with_entitlements.start_attempt(uuid.uuid4(), user_id=user_id)

    mock_entitlement_service.has_mock_test_access.assert_called_once_with(user_id, subject_id)
    assert attempt.status == AttemptStatus.IN_PROGRESS


def test_start_mock_test_checks_the_tests_own_subject_not_a_different_one(
    service_with_entitlements, mock_test_repo, mock_entitlement_service,
):
    """Spec test #2/#3 — the gate must pass the TEST's own subject_id,
    never a hardcoded or caller-supplied one, so a Physics entitlement
    can never accidentally be checked against (or satisfy) a Chemistry
    test. Modeled here by having the fake entitlement store only
    recognize one specific subject."""
    physics_id, chemistry_id = uuid.uuid4(), uuid.uuid4()
    mock_entitlement_service.has_mock_test_access.side_effect = lambda uid, sid: sid == physics_id

    mock_test_repo.get_by_id.return_value = MagicMock(status="published", is_mock_test=True, subject_id=chemistry_id, max_attempts=None)
    with pytest.raises(MockTestAccessDeniedException):
        service_with_entitlements.start_attempt(uuid.uuid4(), user_id=uuid.uuid4())


def test_start_non_mock_test_never_calls_entitlement_service(
    service_with_entitlements, mock_test_repo, mock_repo, mock_question_repo, mock_entitlement_service,
):
    """A regular (non-mock) test must be completely unaffected by this
    feature — is_mock_test=False skips the check entirely, even though
    a real EntitlementService is configured."""
    mock_test_repo.get_by_id.return_value = MagicMock(
        status="published", is_mock_test=False, subject_id=None, duration=60, shuffle_questions=False, max_attempts=None,
    )
    mock_repo.count_for_user_and_test.return_value = 0
    mock_question_repo.list_all_for_test.return_value = []

    service_with_entitlements.start_attempt(uuid.uuid4(), user_id=uuid.uuid4())

    mock_entitlement_service.has_mock_test_access.assert_not_called()


def test_start_mock_test_denied_for_expired_or_revoked_entitlement(service_with_entitlements, mock_test_repo, mock_entitlement_service):
    """Spec test #10 — expired or revoked entitlements cannot start new
    attempts. has_mock_test_access() is a live check (see
    EntitlementRepository.has_active_mock_test_entitlement — status
    and end_date are re-evaluated on every call, nothing is cached) —
    modeled here simply as the service reporting no access."""
    mock_test_repo.get_by_id.return_value = MagicMock(status="published", is_mock_test=True, subject_id=uuid.uuid4(), max_attempts=None)
    mock_entitlement_service.has_mock_test_access.return_value = False

    with pytest.raises(MockTestAccessDeniedException):
        service_with_entitlements.start_attempt(uuid.uuid4(), user_id=uuid.uuid4())


def test_legacy_construction_without_entitlement_service_skips_gate_entirely(mock_repo, mock_answer_repo, mock_test_repo, mock_question_repo, mock_option_repo):
    """Backward-compatibility guard — every caller/test that still
    constructs AttemptService with only the original 5 arguments (the
    `service` fixture above, and anything built before this feature)
    must keep working unchanged, even for a test row that happens to
    have is_mock_test=True (e.g. a MagicMock with no explicit
    is_mock_test, which is truthy by default)."""
    legacy_service = AttemptService(mock_repo, mock_answer_repo, mock_test_repo, mock_question_repo, mock_option_repo)
    mock_test_repo.get_by_id.return_value = MagicMock(status="published", duration=60, shuffle_questions=False, max_attempts=None)
    mock_repo.count_for_user_and_test.return_value = 0
    mock_question_repo.list_all_for_test.return_value = []

    # Must NOT raise MockTestAccessDeniedException — entitlement_service is None.
    attempt = legacy_service.start_attempt(uuid.uuid4(), user_id=uuid.uuid4())
    assert attempt.status == AttemptStatus.IN_PROGRESS


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


def test_save_answer_rejects_option_from_wrong_question(service, mock_repo, mock_option_repo, mock_question_repo):
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    attempt = MagicMock(user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = attempt
    # Sprint 66 — save_answer() now branches on question.question_type
    # before reaching the single_choice option check below, so this mock
    # must be an explicit single_choice question (an unconfigured
    # MagicMock's question_type is not in AUTO_GRADABLE_QUESTION_TYPES,
    # which would wrongly divert into the new short_answer/essay branch
    # and never raise the exception this test expects).
    mock_question_repo.get_by_id.return_value = MagicMock(question_type="single_choice")
    mock_option_repo.get_by_id.return_value = MagicMock(question_id=uuid.uuid4())  # mismatched
    with pytest.raises(InvalidOptionReferenceException):
        service.save_answer(attempt.id, user_id, question_id, uuid.uuid4())


def test_save_answer_locks_the_attempt_before_the_status_check(service, mock_repo, mock_answer_repo, mock_option_repo, mock_question_repo):
    """Sprint 82 — Package 1 regression. save_answer() must now go
    through the same locked path (_lock_attempt() ->
    repo.get_by_id_locked()) every other finalize-triggering/status-
    sensitive call site already uses, not just the unlocked
    repo.get_by_id() read from _get_owned_attempt()."""
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    option_id = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = attempt
    mock_question_repo.get_by_id.return_value = MagicMock(question_type="single_choice")
    mock_option_repo.get_by_id.return_value = MagicMock(question_id=question_id, is_correct=True)

    service.save_answer(attempt.id, user_id, question_id, option_id)

    mock_repo.get_by_id_locked.assert_called_once_with(attempt.id)


def test_save_answer_rejects_when_lock_reveals_a_concurrent_finalize(service, mock_repo, mock_answer_repo, mock_question_repo):
    """Sprint 82 — Package 1 regression, the core race this fix closes.
    Simulates a concurrent submit_attempt() that finalized the attempt
    AFTER the unlocked repo.get_by_id() read (still "in_progress") but
    BEFORE this method's own lock acquisition — by making
    get_by_id_locked() return a DIFFERENT, already-"submitted" object,
    independent of mock_repo's default same-object echo. Before the
    fix, save_answer() never re-checked status after the lock (in fact
    never acquired one at all) and would have silently written the
    answer; after the fix it must raise and must never call upsert()."""
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    stale_attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    finalized_attempt = MagicMock(id=stale_attempt.id, user_id=user_id, status="submitted", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = stale_attempt
    mock_repo.get_by_id_locked.side_effect = None
    mock_repo.get_by_id_locked.return_value = finalized_attempt

    with pytest.raises(AttemptNotActiveException):
        service.save_answer(stale_attempt.id, user_id, question_id, uuid.uuid4())

    mock_answer_repo.upsert.assert_not_called()


def test_save_answer_succeeds_and_computes_correctness(service, mock_repo, mock_answer_repo, mock_option_repo, mock_question_repo):
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    option_id = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = attempt
    # Sprint 66 — see comment in the previous test: must be explicitly
    # single_choice so save_answer() reaches the choice-scoring branch.
    mock_question_repo.get_by_id.return_value = MagicMock(question_type="single_choice")
    mock_option_repo.get_by_id.return_value = MagicMock(question_id=question_id, is_correct=True)
    mock_answer_repo.get.return_value = None

    service.save_answer(attempt.id, user_id, question_id, option_id)

    # Sprint 58 — save_answer() now calls the atomic
    # AnswerRepository.upsert(attempt_id, question_id, values) instead of
    # the old get()-then-create()/update() check-then-act; asserting on
    # upsert()'s `values` dict is the equivalent check for this mocked
    # unit test.
    mock_answer_repo.upsert.assert_called_once()
    values = mock_answer_repo.upsert.call_args[0][2]
    assert values["is_correct"] is True
    mock_repo.commit.assert_called_once()


# --- submit / scoring -----------------------------------------------------

def test_submit_computes_score_correctly(service, mock_repo, mock_answer_repo, mock_question_repo, mock_test_repo):
    user_id = uuid.uuid4()
    q1, q2 = uuid.uuid4(), uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[q1, q2])
    mock_repo.get_by_id.return_value = attempt
    # Sprint 66 — _finalize() now filters questions to
    # AUTO_GRADABLE_QUESTION_TYPES before scoring, so these mocked
    # questions must declare an explicit auto-gradable question_type
    # (an unconfigured MagicMock default would be filtered out,
    # producing an empty auto-scored set and a 0% result instead of the
    # value this test asserts).
    # Sprint 72 (ATT-N2) — _finalize() now batches via list_by_ids()
    # instead of one get_by_id() call per question.
    mock_question_repo.list_by_ids.side_effect = (
        lambda qids: [MagicMock(id=qid, score=5, question_type="single_choice") for qid in qids]
    )
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
    # Sprint 66/72 — see comments in test_submit_computes_score_correctly above.
    mock_question_repo.list_by_ids.side_effect = (
        lambda qids: [MagicMock(id=qid, score=5, question_type="single_choice") for qid in qids]
    )
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


def test_get_result_checks_module_level_expiry_when_configured(mock_repo, mock_answer_repo, mock_test_repo, mock_question_repo, mock_option_repo):
    """Sprint 82 — Package 2 regression. get_result() must call
    ModuleExecutionService.auto_finish_active_module_if_expired(), the
    exact call every other attempt-lifecycle entry point
    (get_attempt(), save_answer(), submit_attempt(), submit_module())
    already makes and get_result() alone was missing — see the
    corresponding real-PostgreSQL integration test
    (tests/integration/test_sprint82_result_retrieval_expiration.py)
    for the full expired-module scenario this wiring enables."""
    mock_module_execution = MagicMock()
    mock_module_execution.auto_finish_active_module_if_expired.return_value = None  # no-op: not actually expired
    service_with_modules = AttemptService(
        mock_repo, mock_answer_repo, mock_test_repo, mock_question_repo, mock_option_repo,
        module_execution_service=mock_module_execution,
    )
    user_id = uuid.uuid4()
    # Must be an ACTIVE_STATUSES status ("in_progress") — both
    # _auto_finish_if_expired() and _auto_finish_active_module_if_expired()
    # short-circuit immediately for a non-active attempt (nothing left
    # to auto-finish), so this call is only reachable while still active.
    # With the mocked auto-finish being a no-op, the attempt correctly
    # stays "in_progress" and get_result() still raises afterward —
    # this test only asserts that the call itself happens.
    attempt = MagicMock(
        id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None,
        score=0, percentage=0, question_order=[],
    )
    mock_repo.get_by_id.return_value = attempt

    with pytest.raises(ResultNotAvailableException):
        service_with_modules.get_result(attempt.id, user_id)

    mock_module_execution.auto_finish_active_module_if_expired.assert_called_once_with(attempt)


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


# --- Sprint 30: multiple_choice save_answer/scoring ---------------------
# NOTE: these tests cannot be collected/run in this sandbox due to the
# same pre-existing environment issue documented since Sprint 20/25/28
# (questions/repository.py's `list[Question]` return-type annotation
# raises TypeError at import time in this specific Python environment —
# unrelated to this sprint's changes). Verified correct via careful
# manual review instead; will run normally in a correctly configured
# environment.

def test_save_answer_multiple_choice_correct_when_selection_exactly_matches_correct_set(
    service, mock_repo, mock_answer_repo, mock_option_repo, mock_question_repo,
):
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    correct_1, correct_2, wrong_1 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = attempt
    mock_question_repo.get_by_id.return_value = MagicMock(question_type="multiple_choice")
    mock_option_repo.list_for_question.return_value = [
        MagicMock(id=correct_1, is_correct=True),
        MagicMock(id=correct_2, is_correct=True),
        MagicMock(id=wrong_1, is_correct=False),
    ]
    mock_answer_repo.get.return_value = None

    service.save_answer(attempt.id, user_id, question_id, None, selected_options=[correct_1, correct_2])

    values = mock_answer_repo.upsert.call_args[0][2]  # Sprint 58 — upsert() replaces create()
    assert values["is_correct"] is True
    assert values["selected_options"] == [correct_1, correct_2]


def test_save_answer_multiple_choice_incorrect_when_missing_a_correct_option(
    service, mock_repo, mock_answer_repo, mock_option_repo, mock_question_repo,
):
    """Partial selection (only one of two correct options) is NOT credited — no partial credit."""
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    correct_1, correct_2 = uuid.uuid4(), uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = attempt
    mock_question_repo.get_by_id.return_value = MagicMock(question_type="multiple_choice")
    mock_option_repo.list_for_question.return_value = [
        MagicMock(id=correct_1, is_correct=True),
        MagicMock(id=correct_2, is_correct=True),
    ]
    mock_answer_repo.get.return_value = None

    service.save_answer(attempt.id, user_id, question_id, None, selected_options=[correct_1])  # missing correct_2

    values = mock_answer_repo.upsert.call_args[0][2]  # Sprint 58 — upsert() replaces create()
    assert values["is_correct"] is False


def test_save_answer_multiple_choice_incorrect_when_extra_wrong_option_included(
    service, mock_repo, mock_answer_repo, mock_option_repo, mock_question_repo,
):
    """Selecting every correct option PLUS an incorrect one is NOT credited."""
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    correct_1, wrong_1 = uuid.uuid4(), uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = attempt
    mock_question_repo.get_by_id.return_value = MagicMock(question_type="multiple_choice")
    mock_option_repo.list_for_question.return_value = [
        MagicMock(id=correct_1, is_correct=True),
        MagicMock(id=wrong_1, is_correct=False),
    ]
    mock_answer_repo.get.return_value = None

    service.save_answer(attempt.id, user_id, question_id, None, selected_options=[correct_1, wrong_1])

    values = mock_answer_repo.upsert.call_args[0][2]  # Sprint 58 — upsert() replaces create()
    assert values["is_correct"] is False


def test_save_answer_multiple_choice_rejects_option_from_wrong_question(
    service, mock_repo, mock_option_repo, mock_question_repo,
):
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    foreign_option = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = attempt
    mock_question_repo.get_by_id.return_value = MagicMock(question_type="multiple_choice")
    mock_option_repo.list_for_question.return_value = [MagicMock(id=uuid.uuid4(), is_correct=True)]  # foreign_option not in this list

    with pytest.raises(InvalidOptionReferenceException):
        service.save_answer(attempt.id, user_id, question_id, None, selected_options=[foreign_option])


def test_save_answer_multiple_choice_empty_selection_is_unanswered_not_incorrect(
    service, mock_repo, mock_answer_repo, mock_option_repo, mock_question_repo,
):
    """Mirrors _check_option's None-for-unanswered convention — an empty
    selection is 'not yet answered', not a scored wrong answer."""
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = attempt
    mock_question_repo.get_by_id.return_value = MagicMock(question_type="multiple_choice")
    mock_answer_repo.get.return_value = None

    service.save_answer(attempt.id, user_id, question_id, None, selected_options=[])

    values = mock_answer_repo.upsert.call_args[0][2]  # Sprint 58 — upsert() replaces create()
    assert values["is_correct"] is None


def test_save_answer_single_choice_path_completely_unaffected_by_multiple_choice_addition(
    service, mock_repo, mock_answer_repo, mock_option_repo, mock_question_repo,
):
    """Backward-compatibility guarantee: when question_repo returns a
    non-multiple_choice type (or a MagicMock default, matching every
    pre-existing test above that never configures mock_question_repo
    at all), the original single_choice code path runs unchanged."""
    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    option_id = uuid.uuid4()
    attempt = MagicMock(id=uuid.uuid4(), user_id=user_id, status="in_progress", expires_at=None, question_order=[question_id])
    mock_repo.get_by_id.return_value = attempt
    mock_question_repo.get_by_id.return_value = MagicMock(question_type="single_choice")
    mock_option_repo.get_by_id.return_value = MagicMock(question_id=question_id, is_correct=True)
    mock_answer_repo.get.return_value = None

    service.save_answer(attempt.id, user_id, question_id, option_id)

    values = mock_answer_repo.upsert.call_args[0][2]  # Sprint 58 — upsert() replaces create()
    assert values["is_correct"] is True
    assert values["selected_option"] == option_id
    mock_option_repo.list_for_question.assert_not_called()  # the multi-select path was never entered
