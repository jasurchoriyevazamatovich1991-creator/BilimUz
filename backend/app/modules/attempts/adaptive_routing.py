"""
Sprint 48 — Generic Adaptive Routing Foundation.

Mirrors attempts/scoring.py's own established pattern (a small
Protocol interface + one deterministic default implementation) — this
sprint deliberately does NOT implement a real adaptive algorithm for
SAT or GRE. A future sprint dedicated to a specific exam's routing
rules would register its own AdaptiveRoutingStrategy implementation
without ever touching AttemptService's control flow, the same way a
future IELTS/GRE-specific ScoringStrategy could be added.

Also provides ModuleAccessGuard — a small, generic service-level
foundation for the access rules Sprint 48's audit identified as
needed before real adaptive transitions can be built (ownership,
assignment, locking, expiry). No public endpoint uses this yet; it
exists so a future sprint implementing real transitions has one
already-tested place to call into, rather than rebuilding these
checks from scratch.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.modules.attempts.models import AttemptModuleProgress, AttemptStatus, TestAttempt
from app.modules.attempts.repository import AttemptRepository
from app.modules.tests.models import ExamModule


@dataclass(frozen=True)
class ModuleCandidate:
    """One module a routing strategy can choose as "next" — deliberately
    minimal: just enough identity/metadata for a strategy to decide
    with, never the module's own Question set (routing decisions
    operate above that level)."""
    module_id: object  # uuid.UUID — kept loosely typed here to avoid a hard uuid import dependency for a pure data-carrier
    order_number: int
    routing_group: str | None
    routing_variant: str | None


@dataclass(frozen=True)
class RoutingDecision:
    """A strategy's answer to "what happens after this module?". next_module_id
    is None when there is no next module (the attempt's adaptive
    portion is complete) — never a sentinel/magic value."""
    next_module_id: object | None  # uuid.UUID | None


class AdaptiveRoutingStrategy(Protocol):
    """Any routing strategy takes the module the candidate just
    finished, that module's performance, and the set of modules that
    could come next, and returns a RoutingDecision. AttemptService (or
    a future module-transition service) only ever talks to this
    interface — it never needs to know which concrete strategy is in
    use, the same separation attempts/scoring.py's ScoringStrategy
    already established for scoring."""

    def decide_next_module(
        self,
        completed_module: ExamModule,
        performance: "ModulePerformance",
        candidates: list[ModuleCandidate],
    ) -> RoutingDecision: ...


@dataclass(frozen=True)
class ModulePerformance:
    """The minimal performance signal a routing strategy needs —
    deliberately generic (no GRE/SAT-specific scoring semantics). A
    real adaptive strategy would likely need more, but this sprint
    only establishes the interface shape, not a real algorithm."""
    correct_count: int
    total_count: int


class SequentialRoutingStrategy:
    """The ONLY strategy this sprint ships — deliberately NOT adaptive.
    Always routes to the candidate with the next-higher order_number,
    completely ignoring `performance`. This exists purely so the
    AdaptiveRoutingStrategy interface has one working, testable
    implementation (per this sprint's explicit "foundation strategy
    may return a deterministic/default next module only if needed for
    tests" allowance) — a real adaptive strategy is out of scope."""

    def decide_next_module(
        self,
        completed_module: ExamModule,
        performance: ModulePerformance,
        candidates: list[ModuleCandidate],
    ) -> RoutingDecision:
        upcoming = [c for c in candidates if c.order_number > completed_module.order_number]
        if not upcoming:
            return RoutingDecision(next_module_id=None)
        next_candidate = min(upcoming, key=lambda c: c.order_number)
        return RoutingDecision(next_module_id=next_candidate.module_id)


class ModuleAccessDeniedException(Exception):
    """Raised by ModuleAccessGuard for any access rule violation. A
    single exception type (not one per rule) is deliberate here — a
    future sprint wiring this into a real endpoint decides its own
    HTTP status/error code mapping; this foundation only needs to
    signal pass/fail with a clear reason."""
    pass


class ModuleAccessGuard:
    """Sprint 48 — generic server-side foundation for the module
    access rules a future adaptive-transition sprint will need:
    ownership, assignment, locking (previous module must be
    submitted), and expiry. No public endpoint calls this yet.

    Deliberately does NOT decide *which* module comes next (that's
    AdaptiveRoutingStrategy's job) — this only answers "is the caller
    allowed to be looking at this specific module progress row right
    now?"."""

    def __init__(self, attempt_repository: AttemptRepository):
        self.attempt_repo = attempt_repository

    def check_access(self, progress: AttemptModuleProgress, attempt: TestAttempt, user_id) -> None:
        """Raises ModuleAccessDeniedException on any violation;
        returns None (no value) when access is allowed — matches this
        project's existing exception-based validation style (see
        e.g. attempts/service.py's own ownership checks)."""
        if attempt.user_id != user_id:
            raise ModuleAccessDeniedException("Bu urinish sizga tegishli emas")
        if progress.attempt_id != attempt.id:
            raise ModuleAccessDeniedException("Bu modul progressi ushbu urinishga tegishli emas")
        if progress.status == AttemptStatus.SUBMITTED.value and progress.submitted_at is not None:
            raise ModuleAccessDeniedException("Bu modul allaqachon yakunlangan")
        if progress.expires_at is not None and progress.expires_at < datetime.now(timezone.utc):
            raise ModuleAccessDeniedException("Bu modul uchun vaqt tugagan")
