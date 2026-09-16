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
