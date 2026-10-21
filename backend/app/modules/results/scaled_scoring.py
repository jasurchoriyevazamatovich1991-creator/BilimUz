"""
Task 4 — exam-specific scaled scoring (IELTS, SAT, GRE). Pure functions:
no I/O and no ORM, so the same rules validate an admin's conversion table
(tests/service.py) and convert a section's raw score when a Result is
created (results/service.py).

No official conversion data lives here. Raw-to-scaled conversion depends
on the exam and the specific test form, so every mapping comes from an
admin-managed, versioned conversion table. When a mapping is missing or
ambiguous the section/overall score is reported with an explicit status
instead of a number.

Arithmetic is exact (fractions.Fraction); floats are never compared.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction

PROFILE_IELTS = "ielts"
PROFILE_SAT = "sat"
PROFILE_GRE = "gre"
SCORING_PROFILES = (PROFILE_IELTS, PROFILE_SAT, PROFILE_GRE)

METHOD_EXACT = "exact"
METHOD_LINEAR = "linear"
CONVERSION_METHODS = (METHOD_EXACT, METHOD_LINEAR)


@dataclass(frozen=True)
class ComponentSpec:
    profile: str
    scale_min: Fraction
    scale_max: Fraction
    step: Fraction
    # False for components that need a human (or AI-assisted) rating
    # rather than a raw-to-scaled table: IELTS Writing/Speaking, GRE AWA.
    table_convertible: bool


COMPONENTS: dict[str, ComponentSpec] = {
    "ielts_listening": ComponentSpec(PROFILE_IELTS, Fraction(0), Fraction(9), Fraction(1, 2), True),
    "ielts_reading": ComponentSpec(PROFILE_IELTS, Fraction(0), Fraction(9), Fraction(1, 2), True),
    "ielts_writing": ComponentSpec(PROFILE_IELTS, Fraction(0), Fraction(9), Fraction(1, 2), False),
    "ielts_speaking": ComponentSpec(PROFILE_IELTS, Fraction(0), Fraction(9), Fraction(1, 2), False),
    "sat_reading_writing": ComponentSpec(PROFILE_SAT, Fraction(200), Fraction(800), Fraction(10), True),
    "sat_math": ComponentSpec(PROFILE_SAT, Fraction(200), Fraction(800), Fraction(10), True),
    "gre_verbal": ComponentSpec(PROFILE_GRE, Fraction(130), Fraction(170), Fraction(1), True),
    "gre_quantitative": ComponentSpec(PROFILE_GRE, Fraction(130), Fraction(170), Fraction(1), True),
    # GRE Analytical Writing is reported 0-6 in half points by human/e-rater
    # scoring — a different scale, kept separate and never table-converted.
    "gre_analytical_writing": ComponentSpec(PROFILE_GRE, Fraction(0), Fraction(6), Fraction(1, 2), False),
}

# Which components make up the overall score of each profile.
IELTS_OVERALL_COMPONENTS = ("ielts_listening", "ielts_reading", "ielts_writing", "ielts_speaking")
SAT_TOTAL_COMPONENTS = ("sat_reading_writing", "sat_math")

# Section statuses (result_sections.scaled_status).
STATUS_SCALED = "scaled"
STATUS_PENDING_MANUAL = "pending_manual_grading"
STATUS_NO_TABLE = "no_conversion_table"
STATUS_OUT_OF_RANGE = "raw_out_of_range"
STATUS_AMBIGUOUS_VARIANT = "ambiguous_variant"
STATUS_NO_COMPONENT = "no_score_component"

# Overall statuses (results.overall_status).
OVERALL_SCALED = "scaled"
OVERALL_PENDING = "pending"
OVERALL_NOT_REPORTED = "not_reported"

MAX_TABLE_ENTRIES = 500
MAX_RAW = Fraction(1000)


class InvalidConversionTable(ValueError):
    """An admin-supplied conversion table breaks a validation rule."""


def components_for_profile(profile: str) -> list[str]:
    return [code for code, spec in COMPONENTS.items() if spec.profile == profile]


def _to_fraction(value, what: str) -> Fraction:
    if isinstance(value, bool):
        raise InvalidConversionTable(f"{what} son bo'lishi kerak")
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise InvalidConversionTable(f"{what} son bo'lishi kerak")
    if not decimal_value.is_finite():
        raise InvalidConversionTable(f"{what} chekli son bo'lishi kerak")
    return Fraction(decimal_value)


def _fmt(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else format(float(value), "g")


def validate_conversion_table(component: str, method: str, entries: list[dict]) -> list[dict]:
    """Validates a table for one score component and returns the canonical
    entries to store: [{"raw": "12", "scaled": "650"}, ...] sorted by raw,
    values as exact decimal strings. Raises InvalidConversionTable."""
    spec = COMPONENTS.get(component)
    if spec is None:
        raise InvalidConversionTable("Bo'limga ballash komponenti belgilanmagan")
    if not spec.table_convertible:
        raise InvalidConversionTable("Bu komponent (Writing/Speaking/AWA) jadval bilan emas, baholovchi tomonidan baholanadi")
    if method not in CONVERSION_METHODS:
        raise InvalidConversionTable(f"method quyidagilardan biri bo'lishi kerak: {', '.join(CONVERSION_METHODS)}")
    if not isinstance(entries, list) or not entries:
        raise InvalidConversionTable("Jadvalda kamida bitta qator bo'lishi kerak")
    if len(entries) > MAX_TABLE_ENTRIES:
        raise InvalidConversionTable(f"Jadvalda ko'pi bilan {MAX_TABLE_ENTRIES} ta qator bo'lishi mumkin")

    pairs: list[tuple[Fraction, Fraction]] = []
    for i, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or "raw" not in entry or "scaled" not in entry:
            raise InvalidConversionTable(f"{i}-qator: 'raw' va 'scaled' maydonlari kerak")
        raw = _to_fraction(entry["raw"], f"{i}-qator raw")
        scaled = _to_fraction(entry["scaled"], f"{i}-qator scaled")
        if raw < 0 or raw > MAX_RAW:
            raise InvalidConversionTable(f"{i}-qator: raw 0 dan {MAX_RAW} gacha bo'lishi kerak")
        if (raw * 100).denominator != 1:
            raise InvalidConversionTable(f"{i}-qator: raw ko'pi bilan 2 xonali kasr bo'lishi mumkin")
        if scaled < spec.scale_min or scaled > spec.scale_max:
            raise InvalidConversionTable(
                f"{i}-qator: scaled {_fmt(spec.scale_min)}–{_fmt(spec.scale_max)} oralig'ida bo'lishi kerak"
            )
        if (scaled / spec.step).denominator != 1:
            raise InvalidConversionTable(f"{i}-qator: scaled {_fmt(spec.step)} qadamli bo'lishi kerak")
        pairs.append((raw, scaled))

    pairs.sort(key=lambda p: p[0])
    for (raw_a, scaled_a), (raw_b, scaled_b) in zip(pairs, pairs[1:]):
        if raw_a == raw_b:
            raise InvalidConversionTable(f"raw={_fmt(raw_a)} ikki marta kiritilgan")
        if scaled_b < scaled_a:
            raise InvalidConversionTable(
                f"Jadval monoton emas: raw {_fmt(raw_a)} → {_fmt(scaled_a)}, raw {_fmt(raw_b)} → {_fmt(scaled_b)}"
            )

    if method == METHOD_EXACT:
        if any(raw.denominator != 1 for raw, _ in pairs):
            raise InvalidConversionTable("'exact' usulida raw butun son bo'lishi kerak")
        expected = list(range(0, int(pairs[-1][0]) + 1))
        present = [int(raw) for raw, _ in pairs]
        if present != expected:
            missing = sorted(set(expected) - set(present))
            raise InvalidConversionTable(
                "'exact' usulida 0 dan eng katta raw gacha har bir qiymat bo'lishi kerak; yetishmaydi: "
                + ", ".join(str(m) for m in missing[:20])
            )
    elif len(pairs) < 2:
        raise InvalidConversionTable("'linear' usulida kamida 2 ta nuqta bo'lishi kerak")

    return [{"raw": _decimal_text(raw), "scaled": _decimal_text(scaled)} for raw, scaled in pairs]


def _decimal_text(value: Fraction) -> str:
    """Exact decimal string for a Fraction known to have a terminating
    decimal expansion (validated: raw has <=2 decimals, scaled is on a
    0.5/1/10 step)."""
    if value.denominator == 1:
        return str(value.numerator)
    return format(Decimal(value.numerator) / Decimal(value.denominator), "f").rstrip("0").rstrip(".")


def _round_to_step(value: Fraction, step: Fraction) -> Fraction:
    """Round half up to the nearest multiple of step (exact)."""
    units = value / step
    floor_units = units.numerator // units.denominator
    remainder = units - floor_units
    rounded = floor_units + (1 if remainder >= Fraction(1, 2) else 0)
    return rounded * step


def convert_raw_score(component: str, method: str, entries: list[dict], raw_score) -> tuple[Fraction | None, str]:
    """Looks up a raw score in a validated table. Returns (scaled, STATUS_SCALED)
    or (None, STATUS_OUT_OF_RANGE). Never extrapolates; 'linear' interpolates
    only between two configured points and rounds to the component's step."""
    spec = COMPONENTS[component]
    raw = _to_fraction(raw_score, "raw")
    points = [(_to_fraction(e["raw"], "raw"), _to_fraction(e["scaled"], "scaled")) for e in entries]
    points.sort(key=lambda p: p[0])

    for point_raw, point_scaled in points:
        if point_raw == raw:
            return point_scaled, STATUS_SCALED
    if method != METHOD_LINEAR:
        return None, STATUS_OUT_OF_RANGE
    for (raw_a, scaled_a), (raw_b, scaled_b) in zip(points, points[1:]):
        if raw_a < raw < raw_b:
            exact = scaled_a + (scaled_b - scaled_a) * (raw - raw_a) / (raw_b - raw_a)
            return _round_to_step(exact, spec.step), STATUS_SCALED
    return None, STATUS_OUT_OF_RANGE


def ielts_overall_band(component_bands: list[Fraction]) -> Fraction:
    """Mean of the four component bands, rounded to the nearest half band;
    a mean ending in .25 rounds up to .5 and one ending in .75 rounds up to
    the next whole band (i.e. round half up to 0.5)."""
    mean = sum(component_bands, Fraction(0)) / len(component_bands)
    return _round_to_step(mean, Fraction(1, 2))


def compute_overall(profile: str, scaled_by_component: dict[str, Fraction | None]) -> tuple[Fraction | None, str]:
    """Overall score from per-component scaled scores (None = not available).
    IELTS: needs all four bands. SAT: Reading and Writing + Math. GRE: no
    combined score is reported (Verbal and Quantitative stand alone)."""
    if profile == PROFILE_GRE:
        return None, OVERALL_NOT_REPORTED
    if profile == PROFILE_IELTS:
        bands = [scaled_by_component.get(c) for c in IELTS_OVERALL_COMPONENTS]
        if any(b is None for b in bands):
            return None, OVERALL_PENDING
        return ielts_overall_band(bands), OVERALL_SCALED
    if profile == PROFILE_SAT:
        parts = [scaled_by_component.get(c) for c in SAT_TOTAL_COMPONENTS]
        if any(p is None for p in parts):
            return None, OVERALL_PENDING
        return sum(parts, Fraction(0)), OVERALL_SCALED
    return None, OVERALL_PENDING
