"""Task 7 — pure provenance/conversion rules (no DB)."""
from fractions import Fraction as F

import pytest

from app.modules.results import official_scoring as osr
from app.modules.results import scaled_scoring as ss


@pytest.mark.parametrize("bands, expected", [
    # IELTS.org worked examples
    ([F(13, 2), F(13, 2), F(5), F(7)], F(13, 2)),          # mean 6.25  -> 6.5
    ([F(4), F(7, 2), F(4), F(4)], F(4)),                   # mean 3.875 -> 4.0
    ([F(13, 2), F(13, 2), F(5), F(13, 2)], F(6)),          # mean 6.125 -> 6.0
    # boundary cases of the stated rule
    ([F(7), F(7), F(7), F(8)], F(7, 1) + F(1, 2)),         # 7.25 -> 7.5
    ([F(7), F(8), F(8), F(8)], F(8)),                      # 7.75 -> 8.0
    ([F(6), F(6), F(6), F(13, 2)], F(6)),                  # 6.125 -> 6.0
    ([F(6), F(13, 2), F(13, 2), F(13, 2)], F(13, 2)),      # 6.375 -> 6.5
    ([F(13, 2), F(13, 2), F(13, 2), F(7)], F(13, 2)),      # 6.625 -> 6.5
    ([F(13, 2), F(7), F(7), F(7)], F(7)),                  # 6.875 -> 7.0
    ([F(9)] * 4, F(9)),
    ([F(0)] * 4, F(0)),
])
def test_ielts_overall_rounding(bands, expected):
    assert ss.ielts_overall_band(bands) == expected


@pytest.mark.parametrize("component, module, raw, expected", [
    ("ielts_listening", None, 16, (F(5), F(11, 2), "scaled")),
    ("ielts_listening", None, 22, (F(5), F(11, 2), "scaled")),
    ("ielts_listening", None, 23, (F(6), F(13, 2), "scaled")),
    ("ielts_listening", None, 34, (F(7), F(15, 2), "scaled")),
    ("ielts_listening", None, 35, (F(8), F(9), "scaled")),
    ("ielts_listening", None, 40, (F(8), F(9), "scaled")),
    ("ielts_listening", "general_training", 23, (F(6), F(13, 2), "scaled")),     # Listening is shared
    ("ielts_listening", None, 15, (None, None, osr.STATUS_BELOW_DOCUMENTED_RANGE)),
    ("ielts_reading", "academic", 15, (F(5), F(11, 2), "scaled")),
    ("ielts_reading", "academic", 14, (None, None, osr.STATUS_BELOW_DOCUMENTED_RANGE)),
    ("ielts_reading", "general_training", 15, (F(4), F(9, 2), "scaled")),
    ("ielts_reading", "general_training", 35, (F(7), F(9), "scaled")),
    ("ielts_reading", "general_training", 29, (F(5), F(11, 2), "scaled")),
    ("ielts_reading", None, 30, (None, None, osr.STATUS_IELTS_MODULE_UNKNOWN)),
    ("ielts_writing", "academic", 30, (None, None, osr.STATUS_IELTS_MODULE_UNKNOWN)),  # no raw conversion exists
])
def test_ielts_indicative_ranges(component, module, raw, expected):
    assert osr.ielts_indicative_band_range(component, module, F(raw), F(40)) == expected


@pytest.mark.parametrize("raw, raw_max", [(F(20), F(39)), (F(41), F(40)), (F(-1), F(40)), (F(41, 2), F(40))])
def test_ielts_indicative_requires_40_mark_scale(raw, raw_max):
    assert osr.ielts_indicative_band_range("ielts_listening", None, raw, raw_max)[2] == osr.STATUS_RAW_SCALE_MISMATCH


def test_registry_metadata_is_complete_and_sat_only():
    for src in osr.SOURCES.values():
        assert src.url.startswith("https://") and src.verified_at == "2026-10-21" and src.supports
    assert sorted(osr.PRACTICE_FORMS) == sorted(f"sat_practice_test_{n}" for n in range(4, 12))
    for form in osr.PRACTICE_FORMS.values():
        assert form.exam == "sat" and form.source_key in osr.SOURCES
        assert form.scoring_guide_url.startswith("https://satsuite.collegeboard.org/media/pdf/scoring-sat-practice-test-")
    assert osr.OFFICIAL_TABLE_PROFILES == ("sat",)
    assert osr.source_dict(osr.IELTS_SOURCE_KEY)["url"].startswith("https://www.ielts.org/")
    assert osr.source_dict("missing") is None and osr.source_dict(None) is None


@pytest.mark.parametrize("profile, bases, expected", [
    ("sat", ["official_practice_test", "official_practice_test"], "official_practice_test"),
    ("sat", ["official_practice_test", "unverified_table"], "unverified_table"),
    ("sat", ["official_practice_test", "estimate"], "estimate"),
    ("ielts", ["estimate", "estimate", "rubric", "rubric"], "estimate"),
    ("ielts", ["unverified_table", "estimate", "rubric", "rubric"], "unverified_table"),
    ("ielts", ["rubric", "rubric", "rubric", "rubric"], "official_rule"),
    ("ielts", ["estimate", None, "rubric", "rubric"], None),
    ("sat", [], None),
])
def test_overall_basis_is_the_weakest_input(profile, bases, expected):
    assert osr.overall_basis(profile, bases) == expected


def _range(n=3):
    return [{"raw": i, "lower": 200 + 20 * i, "upper": 220 + 20 * i} for i in range(n + 1)]


def test_range_table_validation_and_lookup():
    entries = ss.validate_conversion_table("sat_math", "range", _range())
    assert entries[0] == {"raw": "0", "lower": "200", "upper": "220"}
    assert ss.convert_raw_range(entries, 2) == (F(240), F(260), ss.STATUS_SCALED)
    assert ss.convert_raw_range(entries, 4) == (None, None, ss.STATUS_OUT_OF_RANGE)      # no extrapolation
    assert ss.convert_raw_range(entries, 1.5) == (None, None, ss.STATUS_OUT_OF_RANGE)  # no interpolation


@pytest.mark.parametrize("entries", [
    [{"raw": 0, "lower": 200}],
    [{"raw": 0, "lower": 210, "upper": 200}],
    [{"raw": 0, "lower": 195, "upper": 200}],
    [{"raw": 0, "lower": 200, "upper": 810}],
    [{"raw": 0, "lower": 200, "upper": 200}, {"raw": 2, "lower": 210, "upper": 210}],
    [{"raw": 0, "lower": 200, "upper": 200}, {"raw": 0, "lower": 200, "upper": 200}],
    [{"raw": 0, "lower": 300, "upper": 300}, {"raw": 1, "lower": 290, "upper": 310}],
    [{"raw": 0.5, "lower": 200, "upper": 200}],
])
def test_range_table_rejects_bad_data(entries):
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table("sat_reading_writing", "range", entries)


def test_overall_range_rules():
    sat = ss.compute_overall_range("sat", {"sat_reading_writing": (F(470), F(490)), "sat_math": (F(510), F(540))})
    assert sat == (F(980), F(1030), ss.OVERALL_SCALED)
    assert ss.compute_overall_range("sat", {"sat_reading_writing": (F(470), F(490)), "sat_math": None}) == (None, None, ss.OVERALL_PENDING)
    ielts = ss.compute_overall_range("ielts", {
        "ielts_listening": (F(6), F(13, 2)), "ielts_reading": (F(8), F(9)),
        "ielts_writing": (F(7), F(7)), "ielts_speaking": (F(7), F(7)),
    })
    assert ielts == (F(7), F(15, 2), ss.OVERALL_SCALED)
    assert ss.compute_overall_range("gre", {"gre_verbal": (F(150), F(150))}) == (None, None, ss.OVERALL_NOT_REPORTED)
