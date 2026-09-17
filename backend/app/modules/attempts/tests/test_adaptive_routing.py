"""
Sprint 49 — unit tests for PerformanceThresholdRoutingStrategy. Pure
Python, no PostgreSQL required (matches this sprint's explicit
"Tests must not require PostgreSQL" requirement) — uses simple
MagicMock stand-ins for ExamModule (only .routing_group is read).
"""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.attempts.adaptive_routing import (
    ModuleCandidate,
    ModulePerformance,
    PerformanceThresholdRoutingStrategy,
    PerformanceThresholdRule,
    RoutingDecision,
    SequentialRoutingStrategy,
)


def _module(routing_group: str | None):
    return MagicMock(routing_group=routing_group)


def test_below_threshold_selects_lower_variant():
    """1. below threshold selects correct variant"""
    easy_id, hard_id = uuid.uuid4(), uuid.uuid4()
    strategy = PerformanceThresholdRoutingStrategy({
        "verbal": [
            PerformanceThresholdRule(min_ratio=0.0, variant="easy"),
            PerformanceThresholdRule(min_ratio=0.7, variant="hard"),
        ],
    })
    candidates = [
        ModuleCandidate(module_id=easy_id, order_number=1, routing_group="verbal", routing_variant="easy"),
        ModuleCandidate(module_id=hard_id, order_number=1, routing_group="verbal", routing_variant="hard"),
    ]

    decision = strategy.decide_next_module(_module("verbal"), ModulePerformance(correct_count=3, total_count=10), candidates)

    assert decision.next_module_id == easy_id


def test_exactly_threshold_selects_that_tier():
    """2. exactly threshold"""
    easy_id, hard_id = uuid.uuid4(), uuid.uuid4()
    strategy = PerformanceThresholdRoutingStrategy({
        "verbal": [
            PerformanceThresholdRule(min_ratio=0.0, variant="easy"),
            PerformanceThresholdRule(min_ratio=0.7, variant="hard"),
        ],
    })
    candidates = [
        ModuleCandidate(module_id=easy_id, order_number=1, routing_group="verbal", routing_variant="easy"),
        ModuleCandidate(module_id=hard_id, order_number=1, routing_group="verbal", routing_variant="hard"),
    ]

    # 7/10 == 0.7 exactly — inclusive boundary.
    decision = strategy.decide_next_module(_module("verbal"), ModulePerformance(correct_count=7, total_count=10), candidates)

    assert decision.next_module_id == hard_id


def test_above_threshold_selects_higher_variant():
    """3. above threshold"""
    easy_id, hard_id = uuid.uuid4(), uuid.uuid4()
    strategy = PerformanceThresholdRoutingStrategy({
        "verbal": [
            PerformanceThresholdRule(min_ratio=0.0, variant="easy"),
            PerformanceThresholdRule(min_ratio=0.7, variant="hard"),
        ],
    })
    candidates = [
        ModuleCandidate(module_id=easy_id, order_number=1, routing_group="verbal", routing_variant="easy"),
        ModuleCandidate(module_id=hard_id, order_number=1, routing_group="verbal", routing_variant="hard"),
    ]

    decision = strategy.decide_next_module(_module("verbal"), ModulePerformance(correct_count=10, total_count=10), candidates)

    assert decision.next_module_id == hard_id


def test_multiple_thresholds_picks_best_matching_tier():
    """4. multiple thresholds"""
    low_id, mid_id, high_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    strategy = PerformanceThresholdRoutingStrategy({
        "g": [
            PerformanceThresholdRule(min_ratio=0.0, variant="low"),
            PerformanceThresholdRule(min_ratio=0.5, variant="mid"),
            PerformanceThresholdRule(min_ratio=0.8, variant="high"),
        ],
    })
    candidates = [
        ModuleCandidate(module_id=low_id, order_number=1, routing_group="g", routing_variant="low"),
        ModuleCandidate(module_id=mid_id, order_number=1, routing_group="g", routing_variant="mid"),
        ModuleCandidate(module_id=high_id, order_number=1, routing_group="g", routing_variant="high"),
    ]

    decision = strategy.decide_next_module(_module("g"), ModulePerformance(correct_count=6, total_count=10), candidates)

    assert decision.next_module_id == mid_id  # 0.6 satisfies "mid" (0.5) but not "high" (0.8)


def test_arbitrary_routing_group_name_is_not_hardcoded():
    """5. arbitrary routing_group — proves no exam-specific string is baked in."""
    target_id = uuid.uuid4()
    strategy = PerformanceThresholdRoutingStrategy({
        "totally-made-up-group-xyz": [PerformanceThresholdRule(min_ratio=0.0, variant="v")],
    })
    candidates = [ModuleCandidate(module_id=target_id, order_number=1, routing_group="totally-made-up-group-xyz", routing_variant="v")]

    decision = strategy.decide_next_module(_module("totally-made-up-group-xyz"), ModulePerformance(correct_count=1, total_count=1), candidates)

    assert decision.next_module_id == target_id


def test_arbitrary_routing_variant_name_is_not_hardcoded():
    """6. arbitrary routing_variant names — proves no exam-specific string is baked in."""
    target_id = uuid.uuid4()
    strategy = PerformanceThresholdRoutingStrategy({
        "g": [PerformanceThresholdRule(min_ratio=0.0, variant="xyz-variant-123")],
    })
    candidates = [ModuleCandidate(module_id=target_id, order_number=1, routing_group="g", routing_variant="xyz-variant-123")]

    decision = strategy.decide_next_module(_module("g"), ModulePerformance(correct_count=1, total_count=1), candidates)

    assert decision.next_module_id == target_id


def test_empty_variants_returns_none():
    """7. empty variants"""
    strategy = PerformanceThresholdRoutingStrategy({"g": [PerformanceThresholdRule(min_ratio=0.0, variant="v")]})

    decision = strategy.decide_next_module(_module("g"), ModulePerformance(correct_count=1, total_count=1), [])

    assert decision.next_module_id is None


def test_no_matching_rule_returns_none_not_a_guessed_fallback():
    """8. no matching rule — the strategy must never invent a fallback."""
    strategy = PerformanceThresholdRoutingStrategy({"g": [PerformanceThresholdRule(min_ratio=0.9, variant="hard")]})
    candidates = [ModuleCandidate(module_id=uuid.uuid4(), order_number=1, routing_group="g", routing_variant="hard")]

    decision = strategy.decide_next_module(_module("g"), ModulePerformance(correct_count=1, total_count=10), candidates)

    assert decision.next_module_id is None


def test_no_rules_configured_for_group_returns_none():
    """8b. group has no configured rules at all."""
    strategy = PerformanceThresholdRoutingStrategy({"other-group": [PerformanceThresholdRule(min_ratio=0.0, variant="v")]})
    candidates = [ModuleCandidate(module_id=uuid.uuid4(), order_number=1, routing_group="g", routing_variant="v")]

    decision = strategy.decide_next_module(_module("g"), ModulePerformance(correct_count=1, total_count=1), candidates)

    assert decision.next_module_id is None


def test_completed_module_with_no_routing_group_returns_none():
    strategy = PerformanceThresholdRoutingStrategy({"g": [PerformanceThresholdRule(min_ratio=0.0, variant="v")]})
    candidates = [ModuleCandidate(module_id=uuid.uuid4(), order_number=1, routing_group="g", routing_variant="v")]

    decision = strategy.decide_next_module(_module(None), ModulePerformance(correct_count=1, total_count=1), candidates)

    assert decision.next_module_id is None


def test_invalid_performance_zero_total_raises():
    """9. invalid performance input — zero total_count."""
    strategy = PerformanceThresholdRoutingStrategy({"g": [PerformanceThresholdRule(min_ratio=0.0, variant="v")]})
    candidates = [ModuleCandidate(module_id=uuid.uuid4(), order_number=1, routing_group="g", routing_variant="v")]

    with pytest.raises(ValueError):
        strategy.decide_next_module(_module("g"), ModulePerformance(correct_count=0, total_count=0), candidates)


def test_invalid_performance_correct_exceeds_total_raises():
    """9b. invalid performance input — correct_count > total_count."""
    strategy = PerformanceThresholdRoutingStrategy({"g": [PerformanceThresholdRule(min_ratio=0.0, variant="v")]})
    candidates = [ModuleCandidate(module_id=uuid.uuid4(), order_number=1, routing_group="g", routing_variant="v")]

    with pytest.raises(ValueError):
        strategy.decide_next_module(_module("g"), ModulePerformance(correct_count=5, total_count=2), candidates)


def test_invalid_performance_negative_correct_raises():
    """9c. invalid performance input — negative correct_count."""
    strategy = PerformanceThresholdRoutingStrategy({"g": [PerformanceThresholdRule(min_ratio=0.0, variant="v")]})
    candidates = [ModuleCandidate(module_id=uuid.uuid4(), order_number=1, routing_group="g", routing_variant="v")]

    with pytest.raises(ValueError):
        strategy.decide_next_module(_module("g"), ModulePerformance(correct_count=-1, total_count=10), candidates)


def test_result_is_deterministic():
    """10. deterministic result — same input always produces same output."""
    target_id = uuid.uuid4()
    strategy = PerformanceThresholdRoutingStrategy({"g": [PerformanceThresholdRule(min_ratio=0.5, variant="v")]})
    candidates = [ModuleCandidate(module_id=target_id, order_number=1, routing_group="g", routing_variant="v")]
    module = _module("g")
    performance = ModulePerformance(correct_count=8, total_count=10)

    first = strategy.decide_next_module(module, performance, candidates)
    second = strategy.decide_next_module(module, performance, candidates)
    third = strategy.decide_next_module(module, performance, candidates)

    assert first == second == third == RoutingDecision(next_module_id=target_id)


def test_input_collections_are_not_mutated():
    """11. input collections are not mutated — both the rules dict/list
    passed to __init__ and the candidates list passed to
    decide_next_module must be unchanged afterwards."""
    rules_list = [PerformanceThresholdRule(min_ratio=0.0, variant="v")]
    rules_by_group = {"g": rules_list}
    strategy = PerformanceThresholdRoutingStrategy(rules_by_group)

    # Mutate the ORIGINAL collections after construction.
    rules_list.append(PerformanceThresholdRule(min_ratio=0.9, variant="should-not-appear"))
    rules_by_group["another-group"] = [PerformanceThresholdRule(min_ratio=0.0, variant="ignored")]

    target_id = uuid.uuid4()
    candidates = [ModuleCandidate(module_id=target_id, order_number=1, routing_group="g", routing_variant="v")]
    candidates_snapshot = list(candidates)

    decision = strategy.decide_next_module(_module("g"), ModulePerformance(correct_count=1, total_count=1), candidates)

    # The strategy's internal copy is unaffected by the post-construction mutation.
    assert decision.next_module_id == target_id
    # The candidates list itself was never modified by decide_next_module.
    assert candidates == candidates_snapshot


def test_sequential_routing_strategy_remains_compatible():
    """12. SequentialRoutingStrategy remains compatible — Sprint 48's
    original strategy is completely unchanged by this sprint's
    additions to the same file."""
    m1_id, m2_id = uuid.uuid4(), uuid.uuid4()
    strategy = SequentialRoutingStrategy()
    completed = MagicMock(order_number=0)
    candidates = [
        ModuleCandidate(module_id=m1_id, order_number=0, routing_group=None, routing_variant=None),
        ModuleCandidate(module_id=m2_id, order_number=1, routing_group=None, routing_variant=None),
    ]

    decision = strategy.decide_next_module(completed, ModulePerformance(correct_count=5, total_count=10), candidates)

    assert decision.next_module_id == m2_id
