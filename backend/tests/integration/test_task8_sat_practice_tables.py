"""
Task 8 — official SAT paper practice-test tables (Practice Tests 4–11) from
the verified dataset (app/modules/results/data/sat_paper_practice_tables.json),
end to end through the real HTTP API and PostgreSQL.

Sections are built at the real size of these linear forms (R&W 66, Math 54
one-mark items). Expected values are read from the dataset itself; the unit
tests (app/modules/results/tests/test_sat_practice_dataset.py) pin values
transcribed independently from the PDFs.
"""
import uuid

import pytest

from app.modules.results.official_scoring import SAT_DATASET
from app.modules.tests.models import ExamModule
from tests.integration.test_task4_scaled_scoring import API, Ctx, _by_component, _questions, _section, _set_profile, _take, _test
from tests.integration.test_task7_official_conversion import _correct, _table

FORMS = sorted(SAT_DATASET["forms"], key=lambda f: SAT_DATASET["forms"][f]["practice_test_number"])


def _sat(ctx, rw_items=66, math_items=54):
    test = _test(ctx.db, status="published")
    ctx.db.commit()
    assert _set_profile(ctx, test, "sat").status_code == 200
    rw = _section(ctx, test, "Reading and Writing", 0, "sat_reading_writing")
    math = _section(ctx, test, "Math", 1, "sat_math")
    qs = {"rw": _questions(ctx.db, test.id, uuid.UUID(rw["id"]), rw_items),
          "m": _questions(ctx.db, test.id, uuid.UUID(math["id"]), math_items)}
    ctx.db.commit()
    return test, rw, math, qs


def _official(form="sat_practice_test_4", **extra):
    """Official tables are published WITHOUT values — they come from the dataset."""
    return {"method": "range", "conversion_type": "official_practice_test", "test_form": form, **extra}


def _expected(form, section, raw):
    row = SAT_DATASET["forms"][form]["sections"][section]["entries"][raw]
    assert row["raw"] == raw
    return float(row["lower"]), float(row["upper"])


@pytest.mark.parametrize("form", FORMS)
def test_each_form_publishes_its_own_verified_tables_and_scores(client, pg_session, form):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx)
    meta = SAT_DATASET["forms"][form]
    for sec, key, size in ((rw, "reading_writing", 67), (math, "math", 55)):
        r = _table(ctx, sec["id"], _official(form))
        assert r.status_code == 201, r.json()
        data = r.json()["data"]
        assert data["entries"] == [{k: str(v) for k, v in e.items()} for e in meta["sections"][key]["entries"]]
        assert len(data["entries"]) == size
        assert (data["conversion_type"], data["test_form"], data["method"]) == ("official_practice_test", form, "range")
        assert data["source_url"] == meta["source_url"]
        assert meta["guide_title"] in data["source_title"] and "paper, nonadaptive" in data["source_title"]
        assert meta["document_code"] in data["source_version"]
        assert data["source_verified_at"] == meta["verified_at"] == "2026-10-22"
        expected_notes = 1 if (form, key) == ("sat_practice_test_6", "reading_writing") else 0
        assert len(data["source_anomalies"]) == expected_notes

    detail = _take(ctx, test, {**_correct(qs["rw"], 33), **_correct(qs["m"], 27)})
    sec = _by_component(detail)
    rw_lo, rw_up = _expected(form, "reading_writing", 33)
    m_lo, m_up = _expected(form, "math", 27)
    assert (sec["sat_reading_writing"]["raw_score"], sec["sat_reading_writing"]["scaled_score_lower"], sec["sat_reading_writing"]["scaled_score_upper"]) == (33.0, rw_lo, rw_up)
    assert (sec["sat_math"]["raw_score"], sec["sat_math"]["scaled_score_lower"], sec["sat_math"]["scaled_score_upper"]) == (27.0, m_lo, m_up)
    for s in sec.values():
        assert s["score_basis"] == "official_practice_test" and s["source"]["test_form"] == form
    # Total range = sum of the lower values .. sum of the upper values.
    assert (detail["overall_score_lower"], detail["overall_score_upper"]) == (rw_lo + m_lo, rw_up + m_up)
    assert (detail["overall_status"], detail["overall_basis"]) == ("scaled", "official_practice_test")


def test_raw_score_boundaries(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx)
    form = "sat_practice_test_7"
    assert _table(ctx, rw["id"], _official(form)).status_code == 201
    assert _table(ctx, math["id"], _official(form)).status_code == 201

    zero = _take(ctx, test, {})
    assert _by_component(zero)["sat_reading_writing"]["scaled_score"] == 200.0
    assert (zero["overall_score_lower"], zero["overall_score_upper"], zero["overall_scaled_score"]) == (400.0, 400.0, 400.0)

    top = _take(ctx, test, {**_correct(qs["rw"], 66), **_correct(qs["m"], 54)})
    sec = _by_component(top)
    assert (sec["sat_reading_writing"]["raw_score"], sec["sat_reading_writing"]["scaled_score"]) == (66.0, _expected(form, "reading_writing", 66)[0])
    assert (sec["sat_math"]["raw_score"], sec["sat_math"]["scaled_score"]) == (54.0, _expected(form, "math", 54)[0])
    assert top["overall_score_upper"] == 1600.0


def test_practice_test_6_documented_exception(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx)
    r = _table(ctx, rw["id"], _official("sat_practice_test_6"))
    assert r.status_code == 201
    rows = {int(e["raw"]): (int(e["lower"]), int(e["upper"])) for e in r.json()["data"]["entries"]}
    assert (rows[40], rows[41]) == ((540, 580), (530, 590))          # kept exactly as published
    note = r.json()["data"]["source_anomalies"][0]
    assert "raw 41" in note and "530" in note and "540" in note
    m = _table(ctx, math["id"], _official("sat_practice_test_6"))
    assert m.status_code == 201 and m.json()["data"]["source_anomalies"] == []
    listed = client.get(f"{API}/tests/exam-sections/{rw['id']}/conversion-tables", headers=ctx.ah).json()["data"]
    assert listed[0]["source_anomalies"] == [note]

    sec = _by_component(_take(ctx, test, {**_correct(qs["rw"], 41), **_correct(qs["m"], 10)}))
    assert (sec["sat_reading_writing"]["scaled_score_lower"], sec["sat_reading_writing"]["scaled_score_upper"]) == (530.0, 590.0)

    # The exception belongs to the verified source only: the same decreasing
    # row typed into any other table is still rejected.
    hand = [{"raw": i, "lower": lo, "upper": up} for i, (lo, up) in sorted(rows.items())]
    assert _table(ctx, rw["id"], {"method": "range", "conversion_type": "estimate", "entries": hand}).status_code == 422
    other = _sat(ctx)[1]
    assert _table(ctx, other["id"], {"method": "range", "entries": hand}).status_code == 422


def test_sent_values_must_match_the_verified_table(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx)
    exact = [dict(e) for e in SAT_DATASET["forms"]["sat_practice_test_5"]["sections"]["reading_writing"]["entries"]]
    tampered = [dict(e) for e in exact]
    tampered[30]["upper"] += 10
    assert _table(ctx, rw["id"], _official("sat_practice_test_5", entries=tampered)).status_code == 422
    assert _table(ctx, rw["id"], _official("sat_practice_test_5", entries=exact[:-1])).status_code == 422
    assert _table(ctx, rw["id"], _official("sat_practice_test_5", entries=exact)).status_code == 201


@pytest.mark.parametrize("form", ["sat_practice_test_3", "sat_practice_test_12", "sat_practice_test_4_digital", "SAT_PRACTICE_TEST_4", "", None])
def test_unknown_forms_are_rejected(client, pg_session, form):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx, 3, 3)
    assert _table(ctx, rw["id"], _official(form)).status_code == 422


def test_other_invalid_official_requests(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx, 3, 3)
    assert _table(ctx, rw["id"], _official(method="exact")).status_code == 422                     # guides give ranges
    assert _table(ctx, rw["id"], {"method": "range", "conversion_type": "official_guess"}).status_code == 422
    assert _table(ctx, rw["id"], {"method": "exact", "conversion_type": "estimate", "test_form": "sat_practice_test_4",
                                  "entries": [{"raw": 0, "scaled": 200}]}).status_code == 422          # form only on official
    assert _table(ctx, rw["id"], {"method": "range", "entries": []}).status_code == 422                # non-official needs values


def test_paper_tables_are_refused_for_adaptive_sections(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx, 3, 3)
    pg_session.add_all([
        ExamModule(section_id=uuid.UUID(rw["id"]), name="M1", order_number=0),
        ExamModule(section_id=uuid.UUID(rw["id"]), name="M2 hard", order_number=1, routing_variant="hard"),
    ])
    pg_session.commit()
    r = _table(ctx, rw["id"], _official())
    assert r.status_code == 422 and "adaptiv" in r.json()["message"]
    assert _table(ctx, rw["id"], _official(routing_variant="hard")).status_code == 422
    assert _table(ctx, math["id"], _official()).status_code == 201     # the non-adaptive section is fine


def test_forms_are_never_mixed_within_one_test(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx, 3, 3)
    assert _table(ctx, rw["id"], _official("sat_practice_test_4")).status_code == 201
    assert _table(ctx, math["id"], _official("sat_practice_test_5")).status_code == 409
    assert _table(ctx, math["id"], _official("sat_practice_test_4")).status_code == 201


def test_duplicates_and_versioning(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx, 3, 3)
    assert _table(ctx, rw["id"], _official()).status_code == 201
    assert _table(ctx, rw["id"], _official()).status_code == 409                       # identical to current
    est = {"method": "range", "conversion_type": "estimate",
           "entries": [{"raw": i, "lower": 200 + 10 * (i // 2), "upper": 210 + 10 * (i // 2)} for i in range(67)]}   # synthetic, <= 800
    assert _table(ctx, rw["id"], est).json()["data"]["version"] == 2
    again = _table(ctx, rw["id"], _official())                                          # differs from the current (estimate)
    assert again.status_code == 201 and again.json()["data"]["version"] == 3
    listed = client.get(f"{API}/tests/exam-sections/{rw['id']}/conversion-tables", headers=ctx.ah).json()["data"]
    assert [(t["version"], t["is_current"], t["conversion_type"]) for t in listed] == [
        (3, True, "official_practice_test"), (2, False, "estimate"), (1, False, "official_practice_test")]


def test_section_size_must_match_the_form(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx, rw_items=3, math_items=54)
    assert _table(ctx, rw["id"], _official()).status_code == 201
    assert _table(ctx, math["id"], _official()).status_code == 201
    detail = _take(ctx, test, {**_correct(qs["rw"], 3), **_correct(qs["m"], 20)})
    sec = _by_component(detail)
    assert sec["sat_reading_writing"]["scaled_status"] == "raw_scale_mismatch"
    assert (sec["sat_reading_writing"]["scaled_score_lower"], sec["sat_reading_writing"]["score_basis"]) == (None, None)
    assert sec["sat_math"]["scaled_score_lower"] == _expected("sat_practice_test_4", "math", 20)[0]
    assert (detail["overall_status"], detail["overall_score_lower"]) == ("pending", None)


def test_weighted_items_do_not_match_a_practice_form(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx, rw_items=66, math_items=3)
    qs["rw"][0].score = 2
    pg_session.commit()
    assert _table(ctx, rw["id"], _official()).status_code == 201
    detail = _take(ctx, test, _correct(qs["rw"], 1))
    assert _by_component(detail)["sat_reading_writing"]["scaled_status"] == "raw_scale_mismatch"


def test_historical_results_never_change(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx)
    assert _table(ctx, rw["id"], _official("sat_practice_test_8")).status_code == 201
    assert _table(ctx, math["id"], _official("sat_practice_test_8")).status_code == 201
    first = _take(ctx, test, {**_correct(qs["rw"], 20), **_correct(qs["m"], 20)})

    est = {"method": "range", "conversion_type": "estimate",
           "entries": [{"raw": i, "lower": 200 + 10 * (i // 2), "upper": 300 + 10 * (i // 2)} for i in range(67)]}
    assert _table(ctx, rw["id"], est).status_code == 201                                # synthetic v2
    second = _take(ctx, test, {**_correct(qs["rw"], 20), **_correct(qs["m"], 20)})

    again = client.get(f"{API}/results/{first['id']}", headers=ctx.sh).json()["data"]
    assert again == first
    assert _by_component(first)["sat_reading_writing"]["scaled_score_lower"] == _expected("sat_practice_test_8", "reading_writing", 20)[0]
    assert _by_component(second)["sat_reading_writing"]["score_basis"] == "estimate"
    assert _by_component(second)["sat_reading_writing"]["conversion_table_version"] == 2
    assert second["overall_basis"] == "estimate"


def test_unverified_tables_keep_task4_behaviour(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx, 3, 3)
    exact = {"method": "exact", "entries": [{"raw": i, "scaled": 200 + 50 * i} for i in range(6)]}
    assert _table(ctx, rw["id"], exact).status_code == 201
    sec = _by_component(_take(ctx, test, _correct(qs["rw"], 2)))
    assert (sec["sat_reading_writing"]["scaled_score"], sec["sat_reading_writing"]["score_basis"]) == (300.0, "unverified_table")
