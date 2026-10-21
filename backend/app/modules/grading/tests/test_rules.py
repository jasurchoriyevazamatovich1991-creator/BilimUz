"""Task 5 — pure rubric rules (grading/rules.py). Synthetic rubrics only."""
from decimal import Decimal
from fractions import Fraction

import pytest

from app.modules.grading import rules


def crit(key, lo=0, hi=9, step=1, weight=1, label=None):
    return {"key": key, "label": label or key.title(), "min": lo, "max": hi, "step": step, "weight": weight}


FOUR = [crit("a"), crit("b"), crit("c"), crit("d")]


def test_valid_rubric_is_canonicalized():
    out = rules.validate_rubric("ielts_writing", [crit("task_response", 0, 9, Decimal("0.5"), 2, "Task response")], "half_up")
    assert out == [{"key": "task_response", "label": "Task response", "min": "0", "max": "9", "step": "0.5", "weight": "2"}]


@pytest.mark.parametrize("component", ["ielts_listening", "sat_math", "gre_verbal", "unknown"])
def test_rubrics_only_for_manual_components(component):
    with pytest.raises(rules.InvalidRubric):
        rules.validate_rubric(component, FOUR, "half_up")


@pytest.mark.parametrize("criteria", [
    [],
    [crit("a"), crit("a")],                       # duplicate key
    [crit("Bad Key")],                            # invalid key
    [crit("a", 0, 10)],                           # above IELTS 9
    [crit("a", -1, 9)],                           # below 0
    [crit("a", 5, 5)],                            # min == max
    [crit("a", 0, 9, 2)],                         # 9 not reachable in steps of 2
    [crit("a", 0, 9, 0)],                         # zero step
    [crit("a", weight=0)],                        # zero weight
    [crit(f"c{i}") for i in range(11)],           # too many
    [{"key": "a", "label": "", "min": 0, "max": 9, "step": 1}],
    [{"key": "a", "label": "A", "min": "x", "max": 9, "step": 1}],
])
def test_invalid_rubrics_rejected(criteria):
    with pytest.raises(rules.InvalidRubric):
        rules.validate_rubric("ielts_writing", criteria, "half_up")


def test_gre_awa_scale_is_0_to_6():
    rules.validate_rubric("gre_analytical_writing", [crit("analysis", 0, 6, Decimal("0.5"))], "half_up")
    with pytest.raises(rules.InvalidRubric):
        rules.validate_rubric("gre_analytical_writing", [crit("analysis", 0, 9, 1)], "half_up")


def test_unknown_rounding_rejected():
    with pytest.raises(rules.InvalidRubric):
        rules.validate_rubric("ielts_writing", FOUR, "ceil")


CANON = rules.validate_rubric("ielts_writing", FOUR, "half_up")


def test_partial_scores_allowed_for_drafts_but_not_finalization():
    assert rules.validate_scores(CANON, {"a": 6}, require_all=False) == {"a": "6"}
    with pytest.raises(rules.InvalidCriterionScores, match="yetishmaydi"):
        rules.validate_scores(CANON, {"a": 6}, require_all=True)


@pytest.mark.parametrize("scores", [{"a": 10}, {"a": -1}, {"a": "6.5"}, {"zzz": 5}, {"a": "abc"}, {"a": None}, {"a": True}])
def test_invalid_scores_rejected(scores):
    with pytest.raises(rules.InvalidCriterionScores):
        rules.validate_scores(CANON, scores, require_all=False)


def test_scores_must_be_an_object():
    with pytest.raises(rules.InvalidCriterionScores):
        rules.validate_scores(CANON, ["a", 6], require_all=False)


@pytest.mark.parametrize("scores, total, reported", [
    ({"a": 6, "b": 6, "c": 7, "d": 7}, 26, Fraction(13, 2)),   # mean 6.5
    ({"a": 6, "b": 6, "c": 6, "d": 7}, 25, Fraction(13, 2)),   # 6.25 -> 6.5 (half up to 0.5)
    ({"a": 6, "b": 6, "c": 6, "d": 6}, 24, Fraction(6)),
    ({"a": 5, "b": 6, "c": 6, "d": 6}, 23, Fraction(6)),       # 5.75 -> 6.0
    ({"a": 6, "b": 6, "c": 6, "d": 8}, 26, Fraction(13, 2)),   # 6.5
])
def test_answer_score_half_up(scores, total, reported):
    canon = rules.validate_scores(CANON, scores, require_all=True)
    assert rules.compute_answer_score("ielts_writing", CANON, "half_up", canon) == (Fraction(total), reported)


def test_answer_score_floor_mode():
    canon_rubric = rules.validate_rubric("ielts_writing", FOUR, "floor")
    canon = rules.validate_scores(canon_rubric, {"a": 6, "b": 6, "c": 6, "d": 7}, require_all=True)
    assert rules.compute_answer_score("ielts_writing", canon_rubric, "floor", canon)[1] == Fraction(6)   # 6.25 -> 6.0


def test_weighted_criteria():
    rubric = rules.validate_rubric("gre_analytical_writing", [crit("x", 0, 6, 1, 3), crit("y", 0, 6, 1, 1)], "half_up")
    canon = rules.validate_scores(rubric, {"x": 4, "y": 6}, require_all=True)
    # (3*4 + 1*6) / 4 = 4.5
    assert rules.compute_answer_score("gre_analytical_writing", rubric, "half_up", canon) == (Fraction(10), Fraction(9, 2))


def test_section_score_weighted_by_question_weight():
    # IELTS-style: task 1 weight 1 = 6.0, task 2 weight 2 = 7.0 -> 20/3 = 6.67 -> 6.5
    assert rules.compute_section_score("ielts_writing", [(Fraction(1), Fraction(6)), (Fraction(2), Fraction(7))]) == Fraction(13, 2)
    # equal weights 6.0 and 6.5 -> 6.25 -> 6.5
    assert rules.compute_section_score("ielts_writing", [(Fraction(1), Fraction(6)), (Fraction(1), Fraction(13, 2))]) == Fraction(13, 2)


def test_section_score_with_zero_weights_falls_back_to_plain_mean():
    assert rules.compute_section_score("gre_analytical_writing", [(Fraction(0), Fraction(4)), (Fraction(0), Fraction(5))]) == Fraction(9, 2)
