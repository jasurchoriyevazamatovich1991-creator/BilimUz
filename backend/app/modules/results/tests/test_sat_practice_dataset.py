"""Task 8 — the verified SAT paper practice-test dataset (no DB).

Every form, every section, every raw-score row. Pinned values below were
read from the official PDFs' conversion-table page (page 5) and serve as an
independent guard against accidental edits of the JSON file.
"""
import hashlib
import json
from fractions import Fraction as F

import pytest

from app.modules.results import official_scoring as osr
from app.modules.results import scaled_scoring as ss

DATA = osr.SAT_DATASET
FORMS = [f"sat_practice_test_{n}" for n in range(4, 12)]
SECTIONS = {"reading_writing": ("sat_reading_writing", 66), "math": ("sat_math", 54)}
ALL = [(f, s) for f in FORMS for s in SECTIONS]


def _canonical_hash() -> str:
    canon = json.dumps({f: {k: s["entries"] for k, s in v["sections"].items()} for f, v in sorted(DATA["forms"].items())},
                       sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def test_exactly_practice_tests_4_to_11_and_unchanged_values():
    assert sorted(DATA["forms"], key=lambda f: int(f.rsplit("_", 1)[1])) == FORMS
    assert sorted(osr.PRACTICE_FORMS) == sorted(FORMS)
    # Any edit to a value changes this hash; regenerate only from the PDFs
    # with scripts/extract_sat_practice_tables.py.
    assert _canonical_hash() == "98aeedfc89ddf75d947050d519202b3daa0e4b5715c0b0b55913888f03b6654c"


@pytest.mark.parametrize("form", FORMS)
def test_form_metadata(form):
    meta = DATA["forms"][form]
    n = meta["practice_test_number"]
    assert meta["form_id"] == form and form.endswith(f"_{n}")
    assert meta["guide_title"] == f"Scoring Your Paper SAT Practice Test #{n}"
    assert meta["source_url"] == f"https://satsuite.collegeboard.org/media/pdf/scoring-sat-practice-test-{n}-digital.pdf"
    assert meta["verified_at"] == "2026-10-22" and meta["table_page"] == 5
    assert len(meta["pdf_sha256"]) == 64 and meta["document_code"] and 2023 <= meta["copyright_year"] <= 2026
    assert "paper (nonadaptive)" in meta["scope"] and "not an official SAT score" in meta["scope"]
    assert "-layout and -raw" in meta["verification_method"]


@pytest.mark.parametrize("form, section", ALL)
def test_every_row_is_complete_bounded_and_on_10_point_steps(form, section):
    sec = DATA["forms"][form]["sections"][section]
    max_raw = SECTIONS[section][1]
    assert (sec["raw_min"], sec["raw_max"]) == (0, max_raw)
    assert [e["raw"] for e in sec["entries"]] == list(range(max_raw + 1))
    for e in sec["entries"]:
        assert 200 <= e["lower"] <= e["upper"] <= 800
        assert e["lower"] % 10 == 0 and e["upper"] % 10 == 0
    assert (sec["entries"][0]["lower"], sec["entries"][0]["upper"]) == (200, 200)


@pytest.mark.parametrize("form, section", ALL)
def test_monotonic_except_the_single_documented_source_anomaly(form, section):
    entries = DATA["forms"][form]["sections"][section]["entries"]
    decreases = [(b["raw"], f, a[f], b[f]) for a, b in zip(entries, entries[1:]) for f in ("lower", "upper") if b[f] < a[f]]
    recorded = [(a["raw"], a["field"], a["previous_raw_value"], a["value"]) for a in DATA["forms"][form]["sections"][section]["source_anomalies"]]
    assert decreases == recorded
    if (form, section) == ("sat_practice_test_6", "reading_writing"):
        assert decreases == [(41, "lower", 540, 530)]
    else:
        assert decreases == []


@pytest.mark.parametrize("form, section", ALL)
def test_every_row_validates_and_converts_exactly(form, section):
    component, max_raw = SECTIONS[section]
    entries, anomalies = osr.official_practice_table(form, component)
    canonical = ss.validate_conversion_table(component, "range", entries, anomalies)
    assert len(canonical) == max_raw + 1
    for e in entries:
        assert ss.convert_raw_range(canonical, e["raw"]) == (F(e["lower"]), F(e["upper"]), ss.STATUS_SCALED)
    # Out-of-range raw scores are never extrapolated.
    assert ss.convert_raw_range(canonical, max_raw + 1)[2] == ss.STATUS_OUT_OF_RANGE
    assert ss.convert_raw_range(canonical, -1)[2] == ss.STATUS_OUT_OF_RANGE


def test_practice_test_6_exception_is_narrow():
    entries, anomalies = osr.official_practice_table("sat_practice_test_6", "sat_reading_writing")
    assert anomalies == frozenset({(41, "lower", 540, 530)})
    # Without the documented exception the official table would be rejected…
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table("sat_reading_writing", "range", entries)
    # …and the exception does not cover any other decrease.
    other = [dict(e) for e in entries]
    other[50]["lower"] = other[49]["lower"] - 10
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table("sat_reading_writing", "range", other, anomalies)
    changed = [dict(e) for e in entries]
    changed[41]["lower"] = 520                                  # not the published value
    with pytest.raises(ss.InvalidConversionTable):
        ss.validate_conversion_table("sat_reading_writing", "range", changed, anomalies)
    assert osr.official_practice_table("sat_practice_test_6", "sat_math")[1] == frozenset()
    assert len(osr.source_anomaly_notes("sat_practice_test_6", "sat_reading_writing")) == 1
    assert osr.source_anomaly_notes("sat_practice_test_6", "sat_math") == []
    assert osr.source_anomaly_notes("sat_practice_test_4", "sat_reading_writing") == []


@pytest.mark.parametrize("form, section, raw, lower, upper", [
    ("sat_practice_test_4", "reading_writing", 33, 470, 490), ("sat_practice_test_4", "math", 54, 790, 800),
    ("sat_practice_test_4", "reading_writing", 66, 790, 800), ("sat_practice_test_4", "math", 41, 600, 630),
    ("sat_practice_test_5", "math", 9, 270, 330), ("sat_practice_test_5", "reading_writing", 51, 620, 660),
    ("sat_practice_test_6", "reading_writing", 40, 540, 580), ("sat_practice_test_6", "reading_writing", 41, 530, 590),
    ("sat_practice_test_6", "math", 9, 240, 320), ("sat_practice_test_7", "reading_writing", 1, 210, 220),
    ("sat_practice_test_7", "math", 54, 800, 800), ("sat_practice_test_8", "reading_writing", 7, 220, 250),
    ("sat_practice_test_8", "math", 22, 390, 430), ("sat_practice_test_9", "reading_writing", 40, 470, 530),
    ("sat_practice_test_9", "math", 50, 730, 770), ("sat_practice_test_10", "reading_writing", 10, 240, 280),
    ("sat_practice_test_10", "math", 10, 260, 320), ("sat_practice_test_11", "reading_writing", 10, 230, 270),
    ("sat_practice_test_11", "math", 50, 710, 770), ("sat_practice_test_11", "math", 54, 790, 800),
])
def test_pinned_values_from_the_pdfs(form, section, raw, lower, upper):
    row = DATA["forms"][form]["sections"][section]["entries"][raw]
    assert (row["raw"], row["lower"], row["upper"]) == (raw, lower, upper)


def test_forms_differ_so_tables_are_not_interchangeable():
    rw40 = {f: tuple(DATA["forms"][f]["sections"]["reading_writing"]["entries"][40].values()) for f in FORMS}
    assert len(set(rw40.values())) > 1


def test_total_range_is_the_sum_of_section_bounds():
    rw = DATA["forms"]["sat_practice_test_9"]["sections"]["reading_writing"]["entries"][40]
    m = DATA["forms"]["sat_practice_test_9"]["sections"]["math"]["entries"][50]
    lower, upper, status = ss.compute_overall_range("sat", {
        "sat_reading_writing": (F(rw["lower"]), F(rw["upper"])), "sat_math": (F(m["lower"]), F(m["upper"]))})
    assert (lower, upper, status) == (F(470 + 730), F(530 + 770), ss.OVERALL_SCALED)


def test_unknown_forms_and_components_have_no_table():
    assert osr.official_practice_table("sat_practice_test_12", "sat_math") is None
    assert osr.official_practice_table("sat_practice_test_4", "gre_verbal") is None
    assert osr.official_practice_table("sat_practice_test_4", "ielts_reading") is None
