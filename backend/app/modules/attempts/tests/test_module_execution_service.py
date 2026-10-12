"""Sprint 82 — Package 3 (Adaptive Question Routing). Pure unit tests
for ModuleExecutionService._execute_submit()'s performance-ratio
computation — all five repositories mocked, no real DB needed, mirroring
this module's existing test_attempt_service.py style exactly.

Defect under test: the module-level adaptive-routing performance ratio
(ModulePerformance, consumed by PerformanceThresholdRoutingStrategy's
`ratio = correct_count / total_count` in adaptive_routing.py) was
computed from `questions = self.question_repo.list_by_module(...)` —
EVERY question in the module, including short_answer/essay types that
can never have is_correct=True (AttemptService.save_answer()'s
free-text branch always leaves is_correct NULL for them — nothing in
this codebase grades free text automatically; see
attempts/scoring.py's AUTO_GRADABLE_QUESTION_TYPES, the exact same
constant AttemptService._finalize() already uses to exclude them from
the FINAL SCORE for this identical reason, Sprint 66). Including them
here only ever inflated total_count (the ratio's denominator) without
ever being able to inflate correct_count (the numerator), systematically
deflating the routing ratio for any module mixing auto-gradable and
free-text questions.

Fix: `_execute_submit()` now filters `questions` to
AUTO_GRADABLE_QUESTION_TYPES before computing both correct_count and
the total_count passed into `_route_to_next_module()` — mirroring
AttemptService._finalize()'s existing filter exactly.

These tests spy on `service.routing_strategy.decide_next_module` (the
SequentialRoutingStrategy instance ModuleExecutionService falls back to
whenever routing_rule_repo is None — see _select_routing_strategy()) to
directly observe the ModulePerformance object the routing decision is
actually made from, independent of which concrete strategy production
code happens to be configured with.
"""
import uuid
from unittest.mock import MagicMock

from app.modules.attempts.adaptive_routing import RoutingDecision
from app.modules.attempts.module_execution_service import ModuleExecutionService


def _make_service() -> tuple[ModuleExecutionService, dict]:
    mocks = {
        "module_repo": MagicMock(),
        "progress_repo": MagicMock(),
        "question_repo": MagicMock(),
        "answer_repo": MagicMock(),
        "attempt_repo": MagicMock(),
    }
    service = ModuleExecutionService(
        mocks["module_repo"], mocks["progress_repo"], mocks["question_repo"],
        mocks["answer_repo"], mocks["attempt_repo"],
    )
    # Spy on the default SequentialRoutingStrategy instance instead of
    # the real one, so these tests observe exactly what ModulePerformance
    # the routing decision was made from without needing any
    # RoutingThresholdRule setup — routing_rule_repo is None (the
    # default), so _select_routing_strategy() always returns this exact
    # instance (see its own docstring).
    service.routing_strategy = MagicMock()
    service.routing_strategy.decide_next_module.return_value = RoutingDecision(next_module_id=None)
    mocks["routing_strategy"] = service.routing_strategy
    return service, mocks


def _question(question_type: str, score: float = 1.0):
    return MagicMock(id=uuid.uuid4(), question_type=question_type, score=score)


def _answer(question_id, is_correct):
    return MagicMock(question_id=question_id, is_correct=is_correct)


def _progress(module_id, question_order):
    return MagicMock(module_id=module_id, status="in_progress", submitted_at=None, expires_at=None, question_order=question_order)


def test_essay_and_short_answer_questions_excluded_from_routing_denominator():
    """Core Package 3 regression: a module with 2 auto-gradable
    questions (1 correct, 1 wrong) and 1 essay question (never
    auto-graded) must produce a performance ratio of 1/2, NOT 1/3 —
    before the fix, the essay question inflated total_count to 3."""
    service, mocks = _make_service()

    q1 = _question("single_choice")  # answered correctly
    q2 = _question("single_choice")  # answered incorrectly
    q3 = _question("essay")          # never auto-gradable — must be excluded

    module = MagicMock(id=uuid.uuid4(), routing_group=None, section_id=uuid.uuid4())
    attempt = MagicMock(id=uuid.uuid4(), test_id=uuid.uuid4())
    progress = _progress(module.id, [q1.id, q2.id, q3.id])

    mocks["progress_repo"].get_for_attempt_and_module_locked.return_value = progress
    mocks["module_repo"].get_by_id.return_value = module
    mocks["module_repo"].list_for_test.return_value = []
    mocks["progress_repo"].list_for_attempt.return_value = []
    mocks["question_repo"].list_by_module.return_value = [q1, q2, q3]
    mocks["answer_repo"].list_for_attempt.return_value = [
        _answer(q1.id, True),
        _answer(q2.id, False),
        _answer(q3.id, None),  # essay — is_correct is always NULL, never True
    ]

    outcome = service.submit_module(attempt, progress)

    assert outcome == {"completed": True, "next_module_id": None}
    mocks["routing_strategy"].decide_next_module.assert_called_once()
    _, performance, _ = mocks["routing_strategy"].decide_next_module.call_args[0]
    assert performance.total_count == 2, "essay question must not count toward the denominator"
    assert performance.correct_count == 1


def test_module_with_only_essay_questions_falls_back_to_safe_neutral_performance():
    """Boundary case: a module containing ONLY short_answer/essay
    questions must not raise (ZeroDivisionError/ValueError) and must not
    silently route as if every question were eligible — eligible
    total_count is 0, which _route_to_next_module()'s existing
    `total_count <= 0` guard converts to a neutral
    ModulePerformance(correct_count=0, total_count=1)."""
    service, mocks = _make_service()

    q1 = _question("essay")
    q2 = _question("short_answer")

    module = MagicMock(id=uuid.uuid4(), routing_group=None, section_id=uuid.uuid4())
    attempt = MagicMock(id=uuid.uuid4(), test_id=uuid.uuid4())
    progress = _progress(module.id, [q1.id, q2.id])

    mocks["progress_repo"].get_for_attempt_and_module_locked.return_value = progress
    mocks["module_repo"].get_by_id.return_value = module
    mocks["module_repo"].list_for_test.return_value = []
    mocks["progress_repo"].list_for_attempt.return_value = []
    mocks["question_repo"].list_by_module.return_value = [q1, q2]
    mocks["answer_repo"].list_for_attempt.return_value = [
        _answer(q1.id, None),
        _answer(q2.id, None),
    ]

    outcome = service.submit_module(attempt, progress)

    assert outcome == {"completed": True, "next_module_id": None}
    _, performance, _ = mocks["routing_strategy"].decide_next_module.call_args[0]
    assert performance.total_count == 1  # the existing safe fallback, not 0 or 2
    assert performance.correct_count == 0


def test_all_auto_gradable_module_unaffected_by_the_fix():
    """Regression: a module with ONLY auto-gradable questions (the
    overwhelming majority of existing exams) must compute the exact
    same ratio as before this sprint — 2/3, not accidentally narrowed
    by the new filter."""
    service, mocks = _make_service()

    q1 = _question("single_choice")
    q2 = _question("multiple_choice")
    q3 = _question("true_false")

    module = MagicMock(id=uuid.uuid4(), routing_group=None, section_id=uuid.uuid4())
    attempt = MagicMock(id=uuid.uuid4(), test_id=uuid.uuid4())
    progress = _progress(module.id, [q1.id, q2.id, q3.id])

    mocks["progress_repo"].get_for_attempt_and_module_locked.return_value = progress
    mocks["module_repo"].get_by_id.return_value = module
    mocks["module_repo"].list_for_test.return_value = []
    mocks["progress_repo"].list_for_attempt.return_value = []
    mocks["question_repo"].list_by_module.return_value = [q1, q2, q3]
    mocks["answer_repo"].list_for_attempt.return_value = [
        _answer(q1.id, True),
        _answer(q2.id, True),
        _answer(q3.id, False),
    ]

    service.submit_module(attempt, progress)

    _, performance, _ = mocks["routing_strategy"].decide_next_module.call_args[0]
    assert performance.total_count == 3
    assert performance.correct_count == 2


def test_unanswered_eligible_question_still_counts_in_denominator_not_numerator():
    """A single_choice question the student never answered at all (no
    Answer row exists for it) must still count toward total_count (it
    is an eligible, deliverable question) but obviously never toward
    correct_count — unaffected by this sprint, asserted here to pin
    down the exact boundary between "excluded because ineligible type"
    and "not counted because unanswered"."""
    service, mocks = _make_service()

    q1 = _question("single_choice")  # answered correctly
    q2 = _question("single_choice")  # never answered at all

    module = MagicMock(id=uuid.uuid4(), routing_group=None, section_id=uuid.uuid4())
    attempt = MagicMock(id=uuid.uuid4(), test_id=uuid.uuid4())
    progress = _progress(module.id, [q1.id, q2.id])

    mocks["progress_repo"].get_for_attempt_and_module_locked.return_value = progress
    mocks["module_repo"].get_by_id.return_value = module
    mocks["module_repo"].list_for_test.return_value = []
    mocks["progress_repo"].list_for_attempt.return_value = []
    mocks["question_repo"].list_by_module.return_value = [q1, q2]
    mocks["answer_repo"].list_for_attempt.return_value = [_answer(q1.id, True)]  # q2 has no Answer row

    service.submit_module(attempt, progress)

    _, performance, _ = mocks["routing_strategy"].decide_next_module.call_args[0]
    assert performance.total_count == 2
    assert performance.correct_count == 1
