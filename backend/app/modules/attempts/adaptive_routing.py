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
    """The default, deterministic strategy — NOT adaptive. Always
    routes to the candidate with the next-higher order_number,
    completely ignoring `performance`. This exists purely so the
    AdaptiveRoutingStrategy interface has one working, testable
    implementation (per Sprint 48's explicit "foundation strategy
    may return a deterministic/default next module only if needed for
    tests" allowance) — a real adaptive strategy is
    PerformanceThresholdRoutingStrategy, below."""

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


@dataclass(frozen=True)
class PerformanceThresholdRule:
    """One (minimum performance ratio -> routing_variant) rule.
    min_ratio is inclusive: a candidate whose performance ratio is
    exactly equal to min_ratio satisfies this rule (the "exactly
    threshold" boundary case is intentional, not an off-by-one)."""
    min_ratio: float
    variant: str


class PerformanceThresholdRoutingStrategy:
    """Sprint 49 — the first real (non-sequential) implementation of
    the existing AdaptiveRoutingStrategy Protocol from Sprint 48. Pure
    Python: no database, no FastAPI, no repositories, no HTTP, no
    knowledge of any specific exam. Reuses routing_group/routing_variant
    exactly as Sprint 48 defined them on ExamModule/ModuleCandidate —
    no schema change, no new field.

    Configuration is a set of PerformanceThresholdRule lists, one per
    routing_group, supplied by the caller (this class invents no
    exam-specific defaults) — a caller constructs this with its own
    rules for whatever routing_group names its own ExamModule rows
    use; this class never hardcodes any of that.

    Decision logic: within the completed module's own routing_group,
    among the rules whose min_ratio the candidate's performance ratio
    satisfies (ratio >= min_ratio), the rule with the HIGHEST min_ratio
    wins (the "best-matching tier" the candidate qualifies for) — then
    the one candidate module matching that (routing_group,
    routing_variant) pair is selected.

    Deliberately never invents a fallback: if the completed module has
    no routing_group, no rules are configured for that group, no rule's
    threshold is met, or no candidate module actually has the winning
    variant, the result is RoutingDecision(next_module_id=None) — never
    a guessed/default module. Callers that need a fallback must decide
    that explicitly themselves; this strategy will not hide it."""

    def __init__(self, rules_by_group: dict[str, list[PerformanceThresholdRule]]):
        # Defensive copy — the caller's dict/list can be mutated
        # afterwards without ever changing this strategy's behavior
        # (Sprint 49's explicit "do not mutate input collections" /
        # determinism requirement).
        self._rules_by_group: dict[str, list[PerformanceThresholdRule]] = {
            group: list(rules) for group, rules in rules_by_group.items()
        }

    def decide_next_module(
        self,
        completed_module: ExamModule,
        performance: ModulePerformance,
        candidates: list[ModuleCandidate],
    ) -> RoutingDecision:
        if not candidates:
            return RoutingDecision(next_module_id=None)

        if performance.total_count <= 0:
            raise ValueError("ModulePerformance.total_count must be a positive integer to compute a ratio")
        if performance.correct_count < 0 or performance.correct_count > performance.total_count:
            raise ValueError("ModulePerformance.correct_count must be between 0 and total_count")

        group = completed_module.routing_group
        if group is None or group not in self._rules_by_group:
            return RoutingDecision(next_module_id=None)

        ratio = performance.correct_count / performance.total_count

        rules = self._rules_by_group[group]
        matching_rules = [r for r in rules if ratio >= r.min_ratio]
        if not matching_rules:
            return RoutingDecision(next_module_id=None)
        winning_rule = max(matching_rules, key=lambda r: r.min_ratio)

        for candidate in candidates:
            if candidate.routing_group == group and candidate.routing_variant == winning_rule.variant:
                return RoutingDecision(next_module_id=candidate.module_id)

        # A rule matched, but no candidate module actually carries that
        # variant — this is a caller configuration mismatch, not
        # something this strategy should paper over with a guess.
        return RoutingDecision(next_module_id=None)


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
