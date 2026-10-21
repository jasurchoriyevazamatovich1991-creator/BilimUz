"""Task 4 — pure scaled-scoring rules (results/scaled_scoring.py). No DB.
All tables here are synthetic test data, not official conversion tables."""
from decimal import Decimal
from fractions import Fraction

import pytest

from app.modules.results import scaled_scoring as ss


def _rows(*pairs):
    return [{"raw": r, "scaled": s} for r, s in pairs]


# --- table validation -------------------------------------------------------------

def test_exact_table_is_sorted_and_canonicalized():
    out = ss.validate_conversion_table("sat_math", "exact", _rows((2, 400), (0, 200), (1, 300)))
    assert out == [{"raw": "0", "scaled": "200"}, {"raw": "1", "scaled": "300"}, {"raw": "2", "scaled": "400"}]


def test_ielts_half_bands_and_decimal_strings():
    out = ss.validate_conversion_table("ielts_listening", "exact", _rows(("0", "0"), ("1", "2.5"), ("2", Decimal("4.5"))))
    assert [e["scaled"] for e in out] == ["0", "2.5", "4.5"]


@pytest.mark.parametrize("component, scaled", [
    ("ielts_reading", "9.5"), ("ielts_reading", "-0.5"), ("ielts_reading", "6.25"),
    ("sat_math", "190"), ("sat_math", "810"), ("sat_math", "455"),
    ("gre_verbal", "129"), ("gre_verbal", "171"), ("gre_verbal", "150.5"),
])
def test_scaled_out_of_range_or_off_step_rejected(component, scaled):
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table(component, "linear", _rows((0, scaled), (10, scaled)))


@pytest.mark.parametrize("component", ["ielts_writing", "ielts_speaking", "gre_analytical_writing"])
def test_human_rated_components_cannot_have_tables(component):
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table(component, "exact", _rows((0, 0)))


def test_unknown_component_and_method_rejected():
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table(None, "exact", _rows((0, 200)))
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table("sat_math", "nearest", _rows((0, 200), (1, 210)))


def test_duplicate_raw_rejected():
    with pytest.raises(ss.InvalidConversionTable, match="ikki marta"):
        ss.validate_conversion_table("gre_verbal", "linear", _rows((0, 130), (5, 140), (5, 141)))


def test_non_monotonic_rejected():
    with pytest.raises(ss.InvalidConversionTable, match="monoton"):
        ss.validate_conversion_table("sat_math", "exact", _rows((0, 200), (1, 300), (2, 290)))


def test_flat_segments_allowed():
    ss.validate_conversion_table("gre_quantitative", "exact", _rows((0, 130), (1, 130), (2, 131)))


def test_exact_table_with_gap_rejected():
    with pytest.raises(ss.InvalidConversionTable, match="yetishmaydi: 2, 3"):
        ss.validate_conversion_table("sat_math", "exact", _rows((0, 200), (1, 210), (4, 240)))


def test_exact_table_must_start_at_zero_and_use_integers():
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table("sat_math", "exact", _rows((1, 210), (2, 220)))
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table("sat_math", "exact", _rows((0, 200), (0.5, 210)))


def test_linear_needs_two_points():
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table("sat_math", "linear", _rows((0, 200)))


@pytest.mark.parametrize("bad", [-1, 1001, 1.234, "abc", True, None, "NaN", "Infinity"])
def test_invalid_raw_values_rejected(bad):
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table("sat_math", "linear", _rows((bad, 200), (2000, 800)))


def test_malformed_rows_and_empty_tables_rejected():
    for entries in ([], [{"raw": 0}], [{"scaled": 200}], ["0,200"], None):
        with pytest.raises(ss.InvalidConversionTable):
            ss.validate_conversion_table("sat_math", "exact", entries)


def test_too_many_rows_rejected():
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table("gre_verbal", "linear", [{"raw": i, "scaled": 130} for i in range(501)])


# --- conversion -----------------------------------------------------------------------

SAT_EXACT = ss.validate_conversion_table("sat_math", "exact", _rows((0, 200), (1, 250), (2, 330), (3, 420)))
SAT_LINEAR = ss.validate_conversion_table("sat_math", "linear", _rows((0, 200), (10, 500), (20, 800)))


def test_exact_lookup_hits_and_never_extrapolates():
    assert ss.convert_raw_score("sat_math", "exact", SAT_EXACT, 2) == (Fraction(330), ss.STATUS_SCALED)
    assert ss.convert_raw_score("sat_math", "exact", SAT_EXACT, 4) == (None, ss.STATUS_OUT_OF_RANGE)


def test_exact_method_does_not_interpolate_fractional_raw():
    assert ss.convert_raw_score("sat_math", "exact", SAT_EXACT, 1.5) == (None, ss.STATUS_OUT_OF_RANGE)


def test_linear_interpolates_and_rounds_to_step():
    # raw 3 -> 200 + 300*3/10 = 290 exactly
    assert ss.convert_raw_score("sat_math", "linear", SAT_LINEAR, 3) == (Fraction(290), ss.STATUS_SCALED)
    # raw 3.5 -> 305 -> rounds half up to 310
    assert ss.convert_raw_score("sat_math", "linear", SAT_LINEAR, 3.5)[0] == Fraction(310)
    # raw 3.4 -> 302 -> 300
    assert ss.convert_raw_score("sat_math", "linear", SAT_LINEAR, 3.4)[0] == Fraction(300)


def test_linear_outside_configured_points_is_out_of_range():
    assert ss.convert_raw_score("sat_math", "linear", SAT_LINEAR, 21) == (None, ss.STATUS_OUT_OF_RANGE)


def test_ielts_linear_rounds_to_half_band():
    table = ss.validate_conversion_table("ielts_reading", "linear", _rows((10, 4), (20, 6)))
    assert ss.convert_raw_score("ielts_reading", "linear", table, 15)[0] == Fraction(5)
    assert ss.convert_raw_score("ielts_reading", "linear", table, 16)[0] == Fraction(5)       # 5.2 -> 5.0
    assert ss.convert_raw_score("ielts_reading", "linear", table, 17)[0] == Fraction(11, 2)    # 5.4 -> 5.5
    assert ss.convert_raw_score("ielts_reading", "linear", table, 11)[0] == Fraction(4)       # 4.2 -> 4.0
    assert ss.convert_raw_score("ielts_reading", "linear", table, 11.25)[0] == Fraction(9, 2)  # 4.25 -> 4.5


def test_gre_values_stay_on_integer_scale():
    table = ss.validate_conversion_table("gre_verbal", "linear", _rows((0, 130), (3, 135)))
    assert ss.convert_raw_score("gre_verbal", "linear", table, 1)[0] == Fraction(132)  # 131.67 -> 132


# --- overall scores ---------------------------------------------------------------------------

@pytest.mark.parametrize("bands, expected", [
    (("6.5", "6.5", "5", "7"), "6.5"),     # mean 6.25 -> rounds up to 6.5
    (("6.5", "6.5", "6", "6"), "6.5"),     # mean 6.25 -> 6.5
    (("7", "7", "7", "6"), "7"),           # mean 6.75 -> 7.0
    (("6", "6", "6", "6.5"), "6"),         # mean 6.125 -> 6.0
    (("6", "6.5", "6.5", "6.5"), "6.5"),   # mean 6.375 -> 6.5
    (("9", "9", "9", "9"), "9"),
    (("0", "0", "0", "0.5"), "0"),         # mean 0.125 -> 0
])
def test_ielts_overall_half_band_rounding(bands, expected):
    assert ss.ielts_overall_band([Fraction(Decimal(b)) for b in bands]) == Fraction(Decimal(expected))


def test_ielts_overall_requires_all_four_components():
    scaled = {"ielts_listening": Fraction(7), "ielts_reading": Fraction(13, 2), "ielts_writing": None}
    assert ss.compute_overall("ielts", scaled) == (None, ss.OVERALL_PENDING)
    scaled.update(ielts_writing=Fraction(6), ielts_speaking=Fraction(6))
    assert ss.compute_overall("ielts", scaled) == (Fraction(13, 2), ss.OVERALL_SCALED)


def test_sat_total_is_sum_of_two_sections():
    assert ss.compute_overall("sat", {"sat_reading_writing": Fraction(650), "sat_math": Fraction(720)}) == (Fraction(1370), ss.OVERALL_SCALED)
    assert ss.compute_overall("sat", {"sat_reading_writing": Fraction(650), "sat_math": None}) == (None, ss.OVERALL_PENDING)
    assert ss.compute_overall("sat", {"sat_math": Fraction(720)}) == (None, ss.OVERALL_PENDING)


def test_gre_has_no_combined_score():
    assert ss.compute_overall("gre", {"gre_verbal": Fraction(160), "gre_quantitative": Fraction(165)}) == (None, ss.OVERALL_NOT_REPORTED)


def test_components_for_profile():
    assert ss.components_for_profile("sat") == ["sat_reading_writing", "sat_math"]
    assert set(ss.components_for_profile("gre")) == {"gre_verbal", "gre_quantitative", "gre_analytical_writing"}
