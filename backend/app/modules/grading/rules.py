"""
Task 5 — pure rubric rules for manual grading (no I/O, no ORM).

A rubric is admin-defined data: a list of criteria, each with its own
min/max/step and a weight, plus a rounding mode. Nothing here encodes an
official IELTS or GRE rubric; the only exam knowledge used is each
component's reporting scale and step (results/scaled_scoring.COMPONENTS).

- An answer's reported score = weighted mean of its criterion scores,
  rounded to the component's step with the rubric's rounding mode.
- criterion_total = plain sum of the criterion scores (kept separately
  from the reported/scaled score, for auditing).
- A section's score = weighted mean of its answers' reported scores
  (weights = each question's existing `score` field, e.g. IELTS Task 2 = 2,
  Task 1 = 1), rounded half up to the component step.

Exact arithmetic with fractions.Fraction throughout.
"""
import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from app.modules.grading.constants import MAX_CRITERIA, ROUNDING_FLOOR, ROUNDING_HALF_UP, ROUNDING_MODES
from app.modules.results.scaled_scoring import COMPONENTS, MANUAL_COMPONENTS

_KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


class InvalidRubric(ValueError):
    """An admin-supplied rubric breaks a validation rule."""


class InvalidCriterionScores(ValueError):
    """A grader's criterion scores don't fit the rubric."""


def to_fraction(value, what: str, error=InvalidRubric) -> Fraction:
    if isinstance(value, bool) or value is None:
        raise error(f"{what} son bo'lishi kerak")
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise error(f"{what} son bo'lishi kerak")
    if not d.is_finite():
        raise error(f"{what} chekli son bo'lishi kerak")
    return Fraction(d)


def decimal_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    text = format(Decimal(value.numerator) / Decimal(value.denominator), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def round_to_step(value: Fraction, step: Fraction, mode: str) -> Fraction:
    units = value / step
    floor_units = units.numerator // units.denominator
    if mode == ROUNDING_FLOOR:
        return floor_units * step
    return (floor_units + (1 if units - floor_units >= Fraction(1, 2) else 0)) * step


def validate_rubric(component: str, criteria: list[dict], rounding: str) -> list[dict]:
    """Returns canonical criteria [{key, label, min, max, step, weight}] with
    numbers as exact decimal strings. Raises InvalidRubric."""
    if component not in MANUAL_COMPONENTS:
        raise InvalidRubric(f"Rubrika faqat quyidagi komponentlar uchun: {', '.join(MANUAL_COMPONENTS)}")
    if rounding not in ROUNDING_MODES:
        raise InvalidRubric(f"rounding quyidagilardan biri bo'lishi kerak: {', '.join(ROUNDING_MODES)}")
    if not isinstance(criteria, list) or not criteria:
        raise InvalidRubric("Kamida bitta mezon bo'lishi kerak")
    if len(criteria) > MAX_CRITERIA:
        raise InvalidRubric(f"Mezonlar soni {MAX_CRITERIA} tadan oshmasligi kerak")

    spec = COMPONENTS[component]
    out, seen = [], set()
    for i, c in enumerate(criteria, start=1):
        if not isinstance(c, dict):
            raise InvalidRubric(f"{i}-mezon noto'g'ri")
        key = str(c.get("key", "")).strip()
        label = str(c.get("label", "")).strip()
        if not _KEY.match(key):
            raise InvalidRubric(f"{i}-mezon: key lotin kichik harf, raqam va '_' dan iborat bo'lishi kerak (masalan task_achievement)")
        if key in seen:
            raise InvalidRubric(f"'{key}' kaliti takrorlangan")
        seen.add(key)
        if not label or len(label) > 100:
            raise InvalidRubric(f"{i}-mezon: nomi 1–100 belgi bo'lishi kerak")
        lo = to_fraction(c.get("min"), f"{i}-mezon min")
        hi = to_fraction(c.get("max"), f"{i}-mezon max")
        step = to_fraction(c.get("step"), f"{i}-mezon step")
        weight = to_fraction(c.get("weight", 1), f"{i}-mezon weight")
        if lo < spec.scale_min or hi > spec.scale_max or lo >= hi:
            raise InvalidRubric(
                f"{i}-mezon: min < max va {decimal_text(spec.scale_min)}–{decimal_text(spec.scale_max)} oralig'ida bo'lishi kerak"
            )
        if step <= 0 or ((hi - lo) / step).denominator != 1:
            raise InvalidRubric(f"{i}-mezon: step musbat va (max − min) ga karrali bo'lishi kerak")
        if weight <= 0 or weight > 100:
            raise InvalidRubric(f"{i}-mezon: weight 0 dan katta va 100 dan oshmasligi kerak")
        out.append({"key": key, "label": label, "min": decimal_text(lo), "max": decimal_text(hi),
                    "step": decimal_text(step), "weight": decimal_text(weight)})
    return out


def validate_scores(criteria: list[dict], scores: dict, require_all: bool) -> dict[str, str]:
    """Validates a grader's {key: score} against the rubric criteria. Unknown
    keys, out-of-range or off-step values are rejected; with require_all
    every criterion must be present. Returns canonical {key: "6.5"}."""
    if not isinstance(scores, dict):
        raise InvalidCriterionScores("criterion_scores obyekt bo'lishi kerak")
    by_key = {c["key"]: c for c in criteria}
    unknown = set(scores) - set(by_key)
    if unknown:
        raise InvalidCriterionScores(f"Rubrikada yo'q mezon: {', '.join(sorted(unknown))}")
    out = {}
    for key, raw in scores.items():
        c = by_key[key]
        value = to_fraction(raw, f"'{c['label']}' bali", InvalidCriterionScores)
        lo, hi, step = Fraction(Decimal(c["min"])), Fraction(Decimal(c["max"])), Fraction(Decimal(c["step"]))
        if value < lo or value > hi:
            raise InvalidCriterionScores(f"'{c['label']}' bali {c['min']}–{c['max']} oralig'ida bo'lishi kerak")
        if ((value - lo) / step).denominator != 1:
            raise InvalidCriterionScores(f"'{c['label']}' bali {c['step']} qadamli bo'lishi kerak")
        out[key] = decimal_text(value)
    if require_all:
        missing = [c["label"] for c in criteria if c["key"] not in out]
        if missing:
            raise InvalidCriterionScores("Barcha mezonlar baholanishi kerak; yetishmaydi: " + ", ".join(missing))
    return out


def compute_answer_score(component: str, criteria: list[dict], rounding: str, scores: dict[str, str]) -> tuple[Fraction, Fraction]:
    """(criterion_total, reported_score) for a complete set of scores."""
    spec = COMPONENTS[component]
    total = Fraction(0)
    weighted, weight_sum = Fraction(0), Fraction(0)
    for c in criteria:
        value = Fraction(Decimal(scores[c["key"]]))
        weight = Fraction(Decimal(c["weight"]))
        total += value
        weighted += weight * value
        weight_sum += weight
    reported = round_to_step(weighted / weight_sum, spec.step, rounding)
    reported = min(max(reported, spec.scale_min), spec.scale_max)
    return total, reported


def compute_section_score(component: str, weighted_scores: list[tuple[Fraction, Fraction]]) -> Fraction:
    """Weighted mean of (weight, reported_score) pairs, half up to the step."""
    spec = COMPONENTS[component]
    weight_sum = sum((w for w, _ in weighted_scores), Fraction(0))
    if weight_sum <= 0:
        weight_sum = Fraction(len(weighted_scores))
        weighted_scores = [(Fraction(1), s) for _, s in weighted_scores]
    mean = sum((w * s for w, s in weighted_scores), Fraction(0)) / weight_sum
    return round_to_step(mean, spec.step, ROUNDING_HALF_UP)
