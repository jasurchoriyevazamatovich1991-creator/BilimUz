"""
Task 7 — official-source registry and provenance rules for IELTS, Digital
SAT and GRE score conversion. Pure data + pure functions (no I/O, no ORM).

What is (and is not) here, and why:

* IELTS overall band — the official averaging/rounding rule (IELTS.org,
  "IELTS scoring in detail"). Implemented in scaled_scoring.ielts_overall_band.
* IELTS Listening / Academic Reading / General Training Reading — IELTS.org
  publishes only the AVERAGE number of correct answers (out of 40) observed
  at bands 5–8 (4–7 for GT Reading) and states that "the precise number of
  marks needed to achieve these band scores will vary slightly from test
  version to test version". They are therefore used ONLY to produce an
  indicative band RANGE, always labelled as an estimate, never a band.
* IELTS Writing / Speaking — no raw-score conversion exists; they stay on
  the Task 5 rubric workflow.
* Digital SAT — College Board publishes a scoring guide per paper
  (nonadaptive) practice test whose conversion table gives a lower/upper
  range per section. The tables themselves are NOT bundled here: they could
  not be transcribed reliably from the PDFs in this environment, and must be
  entered by an admin from the exact guide (ScoreConversionTable with
  conversion_type='official_practice_test' + test_form). Only the form
  registry (identifiers + guide URLs) lives here.
* GRE — ETS converts raw to scaled scores through equating, accounting for
  section-level adaptation; ETS publishes no raw-to-scaled table. No
  official conversion is supported; admin tables for GRE can only be
  estimates. There is no GRE composite score.

Entries are immutable once released: if a source changes, add a new key
(e.g. "...@2027-01-01") rather than editing an existing one, so a stored
ResultSection.score_source_key keeps meaning exactly what it meant.
"""
from dataclasses import dataclass
from fractions import Fraction

# --- score basis (result_sections.score_basis / results.overall_basis) ---
BASIS_OFFICIAL_RULE = "official_rule"                       # an official scoring rule applied (IELTS overall rounding)
BASIS_OFFICIAL_PRACTICE_TEST = "official_practice_test"     # an official practice-test conversion table
BASIS_ESTIMATE = "estimate"                                 # approximate / indicative
BASIS_UNVERIFIED = "unverified_table"                       # admin table with no verified source
BASIS_RUBRIC = "rubric"                                     # Task 5 human rubric grading
SCORE_BASES = (BASIS_OFFICIAL_RULE, BASIS_OFFICIAL_PRACTICE_TEST, BASIS_ESTIMATE, BASIS_UNVERIFIED, BASIS_RUBRIC)

# --- conversion table types (score_conversion_tables.conversion_type) ---
TABLE_OFFICIAL_PRACTICE_TEST = "official_practice_test"
TABLE_ESTIMATE = "estimate"
TABLE_UNVERIFIED = "unverified"
CONVERSION_TYPES = (TABLE_OFFICIAL_PRACTICE_TEST, TABLE_ESTIMATE, TABLE_UNVERIFIED)

TABLE_TYPE_TO_BASIS = {
    TABLE_OFFICIAL_PRACTICE_TEST: BASIS_OFFICIAL_PRACTICE_TEST,
    TABLE_ESTIMATE: BASIS_ESTIMATE,
    TABLE_UNVERIFIED: BASIS_UNVERIFIED,
}

# --- IELTS modules (tests.ielts_module) ---
IELTS_ACADEMIC = "academic"
IELTS_GENERAL_TRAINING = "general_training"
IELTS_MODULES = (IELTS_ACADEMIC, IELTS_GENERAL_TRAINING)

# --- extra section statuses introduced by Task 7 ---
STATUS_BELOW_DOCUMENTED_RANGE = "below_documented_range"
STATUS_RAW_SCALE_MISMATCH = "raw_scale_mismatch"
STATUS_IELTS_MODULE_UNKNOWN = "ielts_module_unknown"

VERIFIED_AT = "2026-10-21"


@dataclass(frozen=True)
class OfficialSource:
    key: str
    exam: str
    title: str
    url: str
    version: str | None
    verified_at: str
    supports: str


SOURCES: dict[str, OfficialSource] = {
    "ielts_scoring_in_detail@2026-10-21": OfficialSource(
        key="ielts_scoring_in_detail@2026-10-21", exam="ielts",
        title="IELTS scoring in detail (IELTS.org)",
        url="https://www.ielts.org/take-a-test/your-results/ielts-scoring-in-detail",
        version="no date on page (© 2026)", verified_at=VERIFIED_AT,
        supports=("Overall band = mean of the four section bands rounded to the nearest half band (.25 up to .5, "
                  ".75 up to the next whole band). Average marks out of 40 at selected bands for Listening, Academic "
                  "Reading and General Training Reading; thresholds vary slightly by test version (indicative only)."),
    ),
    "collegeboard_sat_paper_practice@2026-10-21": OfficialSource(
        key="collegeboard_sat_paper_practice@2026-10-21", exam="sat",
        title="SAT full-length paper (nonadaptive) practice tests — College Board",
        url="https://satsuite.collegeboard.org/practice/practice-tests/paper",
        version="Practice Tests 4–11 (digital, paper versions); guides © 2023 College Board", verified_at=VERIFIED_AT,
        supports=("Per-practice-test raw-to-section-score conversion with lower and upper values; the total range is the "
                  "sum of the section lower values and of the upper values. For paper (nonadaptive) versions only; a "
                  "simplified, slightly less precise method than Bluebook scoring."),
    ),
    "ets_gre_understand_scores@2026-10-21": OfficialSource(
        key="ets_gre_understand_scores@2026-10-21", exam="gre",
        title="Understanding Your GRE General Test Scores (ETS)",
        url="https://www.ets.org/gre/test-takers/general-test/scores/understand-scores.html",
        version="no date on page (© 2026)", verified_at=VERIFIED_AT,
        supports=("Raw score = number correct; converted to scaled scores through equating that accounts for section-level "
                  "adaptation. No raw-to-scaled table is published."),
    ),
    "ets_gre_score_scales@2026-10-21": OfficialSource(
        key="ets_gre_score_scales@2026-10-21", exam="gre",
        title="GRE General Test scoring (ETS, score users)",
        url="https://www.ets.org/gre/score-users/about/general-test/scoring.html",
        version="no date on page (© 2026)", verified_at=VERIFIED_AT,
        supports="Verbal and Quantitative 130–170 in 1-point increments; Analytical Writing 0–6 in half-point increments; three separate scores.",
    ),
}

IELTS_SOURCE_KEY = "ielts_scoring_in_detail@2026-10-21"


@dataclass(frozen=True)
class PracticeForm:
    form_id: str
    exam: str
    label: str
    scoring_guide_url: str
    source_key: str


def _sat_form(n: int) -> PracticeForm:
    return PracticeForm(
        form_id=f"sat_practice_test_{n}", exam="sat",
        label=f"SAT Practice Test {n} (paper, nonadaptive)",
        scoring_guide_url=f"https://satsuite.collegeboard.org/media/pdf/scoring-sat-practice-test-{n}-digital.pdf",
        source_key="collegeboard_sat_paper_practice@2026-10-21",
    )


# Only forms whose scoring guide was located on the official page. No
# conversion data — admins enter it from the guide itself.
PRACTICE_FORMS: dict[str, PracticeForm] = {f.form_id: f for f in (_sat_form(n) for n in range(4, 12))}

# Which exams may have an "official_practice_test" table at all.
OFFICIAL_TABLE_PROFILES = ("sat",)


# --- IELTS indicative reference points: (average correct out of 40, band) ---
IELTS_RAW_MAX = 40
IELTS_INDICATIVE_POINTS: dict[tuple[str, str | None], tuple[tuple[int, Fraction], ...]] = {
    ("ielts_listening", None): ((16, Fraction(5)), (23, Fraction(6)), (30, Fraction(7)), (35, Fraction(8))),
    ("ielts_reading", IELTS_ACADEMIC): ((15, Fraction(5)), (23, Fraction(6)), (30, Fraction(7)), (35, Fraction(8))),
    ("ielts_reading", IELTS_GENERAL_TRAINING): ((15, Fraction(4)), (23, Fraction(5)), (30, Fraction(6)), (35, Fraction(7))),
}
IELTS_BAND_MAX = Fraction(9)
HALF = Fraction(1, 2)


def ielts_indicative_points(component: str, ielts_module: str | None):
    """The indicative reference points for a component, or None when the
    source gives none (Writing/Speaking) or the Reading module is unknown."""
    if component == "ielts_listening":
        return IELTS_INDICATIVE_POINTS[("ielts_listening", None)]
    if component == "ielts_reading":
        if ielts_module not in IELTS_MODULES:
            return None
        return IELTS_INDICATIVE_POINTS[("ielts_reading", ielts_module)]
    return None


def ielts_indicative_band_range(component: str, ielts_module: str | None, raw: Fraction, raw_max: Fraction):
    """Indicative band RANGE for a Listening/Reading raw score out of 40.

    Returns (lower, upper, status). A raw score at/above the reference
    point for band b and below the next one gives [b, next_b - 0.5]; at/above
    the top point gives [top_b, 9]. Below the lowest documented point there
    is no supported value (no extrapolation). Requires the section to be
    marked out of exactly 40, the scale the published figures refer to."""
    if component == "ielts_reading" and ielts_module not in IELTS_MODULES:
        return None, None, STATUS_IELTS_MODULE_UNKNOWN
    points = ielts_indicative_points(component, ielts_module)
    if points is None:
        return None, None, STATUS_IELTS_MODULE_UNKNOWN
    if raw_max != IELTS_RAW_MAX:
        return None, None, STATUS_RAW_SCALE_MISMATCH
    if raw < 0 or raw > raw_max or raw.denominator != 1:
        return None, None, STATUS_RAW_SCALE_MISMATCH
    if raw < points[0][0]:
        return None, None, STATUS_BELOW_DOCUMENTED_RANGE
    for (threshold, band), (next_threshold, next_band) in zip(points, points[1:]):
        if threshold <= raw < next_threshold:
            return band, next_band - HALF, "scaled"
    return points[-1][1], IELTS_BAND_MAX, "scaled"


_BASIS_STRENGTH = {BASIS_UNVERIFIED: 0, BASIS_ESTIMATE: 1, BASIS_OFFICIAL_PRACTICE_TEST: 2, BASIS_RUBRIC: 2, BASIS_OFFICIAL_RULE: 2}


def overall_basis(profile: str, component_bases: list[str | None]) -> str | None:
    """The weakest basis among the components that make up an overall score.
    An overall is never more authoritative than its least reliable input."""
    bases = [b for b in component_bases if b is not None]
    if not bases or len(bases) != len(component_bases):
        return None
    weakest = min(bases, key=lambda b: _BASIS_STRENGTH.get(b, 0))
    if _BASIS_STRENGTH.get(weakest, 0) < 2:
        return weakest
    if profile == "sat":
        return BASIS_OFFICIAL_PRACTICE_TEST
    # IELTS: the official overall rounding rule applied to rubric/table bands.
    return BASIS_OFFICIAL_RULE


def source_dict(key: str | None) -> dict | None:
    src = SOURCES.get(key) if key else None
    if src is None:
        return None
    return {"key": src.key, "title": src.title, "url": src.url, "version": src.version, "verified_at": src.verified_at}
