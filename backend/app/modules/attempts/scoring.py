"""
Sprint 45 — Scoring Strategy foundation.

A minimal, extractable strategy interface around the scoring
calculation AttemptService._finalize() already performed inline. This
sprint deliberately does NOT add SAT/IELTS/GRE-specific scoring,
adaptive logic, or AI grading (out of scope — see Sprint 45 prompt
items 14/15). What it DOES do is give that one calculation a name and
a pluggable seam, so a future sprint can register a different strategy
(e.g. a band-score strategy for IELTS) without touching
AttemptService's control flow again.

PercentageScoringStrategy.calculate() reproduces
AttemptService._finalize()'s exact prior arithmetic byte-for-byte
(same source line moved, not rewritten) — this is a pure extraction,
not a behavior change. Every existing test (Physics, National
Certificate) computes an identical score/percentage before and after
this sprint.
"""
from dataclasses import dataclass
from typing import Protocol

from app.modules.attempts.models import Answer
from app.modules.questions.models import Question

# Sprint 66 — the single source of truth for "which question types can
# be automatically scored today". short_answer/essay are deliberately
# excluded: Answer.text_answer (Sprint 45) has no automatic-correctness
# determination anywhere in the codebase, so is_correct stays NULL for
# them forever (see save_answer()'s free-text branch in service.py).
# Before this sprint, AttemptService._finalize() still summed their
# question.score into the scoring denominator (total_possible) even
# though they could never contribute to the numerator — silently
# deflating the automatic score of any exam containing one. This
# constant is consumed by AttemptService._finalize() (the ONLY call
# site changed this sprint) to filter the question list BEFORE handing
# it to a ScoringStrategy — the strategy interface/arithmetic below is
# untouched, and the other two existing callers of
# DEFAULT_SCORING_STRATEGY.calculate() (ModuleExecutionService.
# submit_module()'s own — currently unused — scoring_result, and
# ResultService._create_result_sections()'s per-section raw_score) are
# deliberately NOT filtered here, since neither was named in this
# sprint's scope (ResultSection redesign is explicitly out of scope;
# module-level scoring_result is presently a dead, unused local value).
AUTO_GRADABLE_QUESTION_TYPES = frozenset({"single_choice", "multiple_choice", "true_false"})


@dataclass(frozen=True)
class ScoringResult:
    score: float
    percentage: float


class ScoringStrategy(Protocol):
    """Any scoring strategy takes the attempt's questions and answers
    and returns a (score, percentage) pair. AttemptService only ever
    talks to this interface — it never needs to know which concrete
    strategy is in use."""

    def calculate(self, questions: list[Question], answers: list[Answer]) -> ScoringResult: ...


class PercentageScoringStrategy:
    """The platform default today, and the only strategy this sprint
    ships: total points earned / total points possible, as a
    percentage. Identical to AttemptService._finalize()'s prior inline
    calculation — extracted, not changed."""

    def calculate(self, questions: list[Question], answers: list[Answer]) -> ScoringResult:
        correct_by_question = {a.question_id: a.is_correct for a in answers}
        total_score = sum(float(q.score) for q in questions if correct_by_question.get(q.id) is True)
        total_possible = sum(float(q.score) for q in questions) or 1.0
        percentage = round((total_score / total_possible) * 100, 2)
        return ScoringResult(score=total_score, percentage=percentage)


# The one strategy instance AttemptService uses today. A future sprint
# adding e.g. IELTS band scoring would introduce a way to select a
# strategy per Test (out of scope here — this sprint only establishes
# that AttemptService depends on the ScoringStrategy interface, not on
# inline arithmetic).
DEFAULT_SCORING_STRATEGY = PercentageScoringStrategy()
