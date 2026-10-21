"""
Task 7 — official-source-based conversion and score provenance, against real
PostgreSQL (migrations up to 0028) through the real HTTP API.

IELTS figures used here are the published IELTS.org reference points
(official_scoring.IELTS_INDICATIVE_POINTS). Every SAT/GRE conversion table
in this file is SYNTHETIC test data — never official College Board / ETS
numbers.
"""
import uuid

from app.modules.results.models import Result, ResultSection
from tests.integration.test_task4_scaled_scoring import (
    API, Ctx, _by_component, _questions, _section, _set_profile, _take, _test,
)

IELTS_URL = "https://www.ielts.org/take-a-test/your-results/ielts-scoring-in-detail"
SAT4_GUIDE = "https://satsuite.collegeboard.org/media/pdf/scoring-sat-practice-test-4-digital.pdf"


def _profile(ctx, test, profile, **extra):
    return ctx.client.put(f"{API}/tests/{test.id}/scoring-profile", json={"scoring_profile": profile, **extra}, headers=ctx.ah)


def _table(ctx, section_id, body):
    return ctx.client.post(f"{API}/tests/exam-sections/{section_id}/conversion-tables", json=body, headers=ctx.ah)


def _range_rows(n, start, width):
    """Synthetic monotonic range table 0..n (NOT official data)."""
    return [{"raw": i, "lower": start + 20 * i, "upper": start + 20 * i + width} for i in range(n + 1)]


def _ielts(ctx, module="academic", listening=40, reading=40, manual=True):
    test = _test(ctx.db, status="published")
    ctx.db.commit()
    assert _profile(ctx, test, "ielts", ielts_module=module).status_code == 200
    out = {"test": test}
    lst = _section(ctx, test, "Listening", 0, "ielts_listening")
    rdg = _section(ctx, test, "Reading", 1, "ielts_reading")
    out["L"] = _questions(ctx.db, test.id, uuid.UUID(lst["id"]), listening)
    out["R"] = _questions(ctx.db, test.id, uuid.UUID(rdg["id"]), reading)
    out["sections"] = {"L": lst, "R": rdg}
    if manual:
        w = _section(ctx, test, "Writing", 2, "ielts_writing")
        s = _section(ctx, test, "Speaking", 3, "ielts_speaking")
        out["W"] = _questions(ctx.db, test.id, uuid.UUID(w["id"]), 1, qtype="essay")
        out["S"] = _questions(ctx.db, test.id, uuid.UUID(s["id"]), 1, qtype="essay")
    ctx.db.commit()
    return out


def _correct(questions, n):
    return {q: True for q in questions[:n]}


def _rubric(ctx, component):
    r = ctx.client.post(f"{API}/grading/rubrics", json={
        "score_component": component, "name": component,
        "criteria": [{"key": "c", "label": "C", "min": 0, "max": 9, "step": 1}],
        "rounding": "half_up", "is_validated": False,
    }, headers=ctx.ah)
    assert r.status_code == 201, r.json()


def _grade(ctx, attempt_id, question, score):
    url = f"{API}/grading/submissions/{attempt_id}/{question.id}"
    assert ctx.client.put(f"{url}/draft", json={"criterion_scores": {"c": score}}, headers=ctx.ah).status_code == 200
    assert ctx.client.post(f"{url}/finalize", headers=ctx.ah).status_code == 200


# --- IELTS ---------------------------------------------------------------------------------

def test_ielts_indicative_ranges_and_overall_estimate(client, pg_session):
    ctx = Ctx(client, pg_session)
    t = _ielts(ctx, "academic")
    detail = _take(ctx, t["test"], {**_correct(t["L"], 25), **_correct(t["R"], 35), t["W"][0]: "essay", t["S"][0]: "notes"})
    sec = _by_component(detail)
    L, R = sec["ielts_listening"], sec["ielts_reading"]
    assert (L["raw_score"], L["scaled_score"], L["scaled_score_lower"], L["scaled_score_upper"]) == (25.0, None, 6.0, 6.5)
    assert (R["scaled_score_lower"], R["scaled_score_upper"]) == (8.0, 9.0)
    for s in (L, R):
        assert s["score_basis"] == "estimate" and s["scaled_status"] == "scaled"
        assert s["source"]["url"] == IELTS_URL and s["source"]["verified_at"] == "2026-10-21"
        assert s["conversion_table_version"] is None
    assert sec["ielts_writing"]["scaled_status"] == "pending_manual_grading" and sec["ielts_writing"]["score_basis"] is None
    assert (detail["overall_status"], detail["overall_scaled_score"], detail["overall_basis"]) == ("pending", None, None)

    # Task 5 regression: finalizing Writing/Speaking completes the overall.
    _rubric(ctx, "ielts_writing")
    _rubric(ctx, "ielts_speaking")
    attempt_id = detail["attempt_id"]
    _grade(ctx, attempt_id, t["W"][0], 7)
    _grade(ctx, attempt_id, t["S"][0], 7)
    detail = ctx.client.get(f"{API}/results/{detail['id']}", headers=ctx.sh).json()["data"]
    sec = _by_component(detail)
    assert (sec["ielts_writing"]["scaled_score"], sec["ielts_writing"]["score_basis"]) == (7.0, "rubric")
    # lowers: (6 + 8 + 7 + 7) / 4 = 7.0 -> 7.0 ; uppers: (6.5 + 9 + 7 + 7) / 4 = 7.375 -> 7.5
    assert detail["overall_status"] == "scaled"
    assert (detail["overall_score_lower"], detail["overall_score_upper"], detail["overall_scaled_score"]) == (7.0, 7.5, None)
    assert detail["overall_basis"] == "estimate"            # never better than its weakest input
    assert detail["is_provisional"] is True                 # unvalidated rubric (Task 5 rule unchanged)


def test_ielts_general_training_reading_differs_from_academic(client, pg_session):
    ctx = Ctx(client, pg_session)
    gt = _ielts(ctx, "general_training", manual=False)
    sec = _by_component(_take(ctx, gt["test"], {**_correct(gt["L"], 30), **_correct(gt["R"], 30)}))
    assert (sec["ielts_reading"]["scaled_score_lower"], sec["ielts_reading"]["scaled_score_upper"]) == (6.0, 6.5)
    assert (sec["ielts_listening"]["scaled_score_lower"], sec["ielts_listening"]["scaled_score_upper"]) == (7.0, 7.5)

    ac = _ielts(ctx, "academic", manual=False)
    sec = _by_component(_take(ctx, ac["test"], {**_correct(ac["L"], 30), **_correct(ac["R"], 30)}))
    assert (sec["ielts_reading"]["scaled_score_lower"], sec["ielts_reading"]["scaled_score_upper"]) == (7.0, 7.5)


def test_ielts_boundaries_unknown_module_and_wrong_scale(client, pg_session):
    ctx = Ctx(client, pg_session)
    t = _ielts(ctx, None, manual=False)            # Academic/GT not chosen
    sec = _by_component(_take(ctx, t["test"], {**_correct(t["L"], 15), **_correct(t["R"], 30)}))
    assert sec["ielts_listening"]["scaled_status"] == "below_documented_range"       # 15 < 16: no extrapolation
    assert sec["ielts_listening"]["scaled_score_lower"] is None and sec["ielts_listening"]["score_basis"] is None
    assert sec["ielts_reading"]["scaled_status"] == "ielts_module_unknown"

    short = _ielts(ctx, "academic", listening=20, reading=40, manual=False)
    sec = _by_component(_take(ctx, short["test"], {**_correct(short["L"], 16), **_correct(short["R"], 16)}))
    assert sec["ielts_listening"]["scaled_status"] == "raw_scale_mismatch"           # published figures are out of 40
    assert (sec["ielts_reading"]["scaled_score_lower"], sec["ielts_reading"]["scaled_score_upper"]) == (5.0, 5.5)


def test_ielts_module_setting_rules(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    assert _profile(ctx, test, "ielts", ielts_module="academic").json()["data"]["ielts_module"] == "academic"
    assert _profile(ctx, test, "ielts").json()["data"]["ielts_module"] == "academic"           # omitted = unchanged
    assert _profile(ctx, test, "ielts", ielts_module="general_training").json()["data"]["ielts_module"] == "general_training"
    assert _profile(ctx, test, "ielts", ielts_module="foundation").status_code == 422
    assert _profile(ctx, test, "sat", ielts_module="academic").status_code == 422
    assert _profile(ctx, test, "sat").json()["data"]["ielts_module"] is None                    # cleared for other profiles


def test_admin_table_takes_precedence_and_is_labelled_unverified(client, pg_session):
    ctx = Ctx(client, pg_session)
    t = _ielts(ctx, "academic", manual=False)
    rows = [{"raw": i, "scaled": min(9, i // 4 * 0.5 + 1) if i else 0} for i in range(41)]
    r = _table(ctx, t["sections"]["L"]["id"], {"method": "exact", "entries": rows})
    assert r.status_code == 201 and r.json()["data"]["conversion_type"] == "unverified"
    # Official practice-test tables are refused for IELTS (none verified).
    assert _table(ctx, t["sections"]["R"]["id"], {"method": "range", "conversion_type": "official_practice_test",
                                                  "test_form": "sat_practice_test_4",
                                                  "entries": [{"raw": 0, "lower": 1, "upper": 2}]}).status_code == 422
    sec = _by_component(_take(ctx, t["test"], {**_correct(t["L"], 25), **_correct(t["R"], 25)}))
    L = sec["ielts_listening"]
    assert (L["scaled_score"], L["score_basis"], L["conversion_table_version"], L["source"]) == (4.0, "unverified_table", 1, None)
    assert sec["ielts_reading"]["score_basis"] == "estimate"


# --- SAT -----------------------------------------------------------------------------------

def _sat(ctx, n=3):
    test = _test(ctx.db, status="published")
    ctx.db.commit()
    assert _set_profile(ctx, test, "sat").status_code == 200
    rw = _section(ctx, test, "Reading and Writing", 0, "sat_reading_writing")
    math = _section(ctx, test, "Math", 1, "sat_math")
    qs = {"rw": _questions(ctx.db, test.id, uuid.UUID(rw["id"]), n), "m": _questions(ctx.db, test.id, uuid.UUID(math["id"]), n)}
    ctx.db.commit()
    return test, rw, math, qs


def _official(rows, form="sat_practice_test_4", **extra):
    return {"method": "range", "conversion_type": "official_practice_test", "test_form": form, "entries": rows, **extra}


def test_sat_practice_test_ranges_and_total(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx)
    r = _table(ctx, rw["id"], _official(_range_rows(3, 200, 20), source_url="https://evil.example/fake"))
    assert r.status_code == 201, r.json()
    data = r.json()["data"]
    # The source comes from the registry, never from the request.
    assert (data["conversion_type"], data["test_form"], data["source_url"]) == ("official_practice_test", "sat_practice_test_4", SAT4_GUIDE)
    assert data["entries"][1] == {"raw": "1", "lower": "220", "upper": "240"}
    assert _table(ctx, math["id"], _official(_range_rows(3, 300, 0))).status_code == 201

    detail = _take(ctx, test, {**_correct(qs["rw"], 2), **_correct(qs["m"], 1)})
    sec = _by_component(detail)
    RW, M = sec["sat_reading_writing"], sec["sat_math"]
    assert (RW["scaled_score"], RW["scaled_score_lower"], RW["scaled_score_upper"]) == (None, 240.0, 260.0)
    assert (M["scaled_score"], M["scaled_score_lower"], M["scaled_score_upper"]) == (320.0, 320.0, 320.0)   # lower == upper
    for s in (RW, M):
        assert s["score_basis"] == "official_practice_test"
        assert s["source"]["test_form"] == "sat_practice_test_4" and "nonadaptive" in s["source"]["test_form_label"]
        assert s["source"]["url"] == SAT4_GUIDE
    assert (detail["overall_score_lower"], detail["overall_score_upper"], detail["overall_scaled_score"]) == (560.0, 580.0, None)
    assert (detail["overall_status"], detail["overall_basis"]) == ("scaled", "official_practice_test")


def test_sat_official_table_validation_and_form_isolation(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx)
    good = _range_rows(3, 200, 20)
    cases = [
        _official(good, form=None),                                    # form required
        _official(good, form="sat_practice_test_99"),                  # unknown form
        _official(good, form="sat_practice_test_4", method="exact"),   # guides give ranges
        _official([{"raw": 0, "lower": 200, "upper": 210}, {"raw": 2, "lower": 220, "upper": 230}]),   # gap
        _official([{"raw": 0, "lower": 230, "upper": 220}]),           # lower > upper
        _official([{"raw": 0, "lower": 205, "upper": 210}]),           # off the 10-point step
        _official([{"raw": 0, "lower": 300, "upper": 310}, {"raw": 1, "lower": 290, "upper": 320}]),  # not monotonic
        {"method": "range", "conversion_type": "official_guess", "entries": good},
        {"method": "exact", "conversion_type": "estimate", "test_form": "sat_practice_test_4",
         "entries": [{"raw": 0, "scaled": 200}]},                      # form only for official tables
    ]
    for body in cases:
        assert _table(ctx, rw["id"], body).status_code == 422, body
    assert _table(ctx, rw["id"], _official(good)).status_code == 201
    # A different practice test's table can't be mixed into the same test.
    clash = _table(ctx, math["id"], _official(good, form="sat_practice_test_5"))
    assert clash.status_code == 409
    assert _table(ctx, math["id"], _official(good, form="sat_practice_test_4")).status_code == 201


def test_sat_official_table_refuses_routing_variant(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx)
    from app.modules.tests.models import ExamModule
    pg_session.add(ExamModule(section_id=uuid.UUID(rw["id"]), name="M2", order_number=1, routing_variant="hard"))
    pg_session.commit()
    body = _official(_range_rows(3, 200, 20), routing_variant="hard")
    assert _table(ctx, rw["id"], body).status_code == 422


def test_sat_unverified_table_mixed_with_official_gives_unverified_total(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx)
    assert _table(ctx, rw["id"], _official(_range_rows(3, 200, 20))).status_code == 201
    assert _table(ctx, math["id"], {"method": "exact", "entries": [{"raw": i, "scaled": 200 + 100 * i} for i in range(4)]}).status_code == 201
    detail = _take(ctx, test, {**_correct(qs["rw"], 3), **_correct(qs["m"], 3)})
    assert _by_component(detail)["sat_math"]["score_basis"] == "unverified_table"
    assert (detail["overall_score_lower"], detail["overall_score_upper"], detail["overall_basis"]) == (760.0, 780.0, "unverified_table")


# --- GRE -----------------------------------------------------------------------------------

def test_gre_has_no_official_conversion_or_composite(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session, status="published")
    pg_session.commit()
    assert _set_profile(ctx, test, "gre").status_code == 200
    v = _section(ctx, test, "Verbal", 0, "gre_verbal")
    q = _section(ctx, test, "Quant", 1, "gre_quantitative")
    vq = _questions(pg_session, test.id, uuid.UUID(v["id"]), 2)
    _questions(pg_session, test.id, uuid.UUID(q["id"]), 2)
    pg_session.commit()
    rows = [{"raw": i, "scaled": 130 + 20 * i} for i in range(3)]
    assert _table(ctx, v["id"], {"method": "exact", "conversion_type": "official_practice_test", "test_form": "sat_practice_test_4",
                                 "entries": rows}).status_code == 422
    est = _table(ctx, v["id"], {"method": "exact", "conversion_type": "estimate", "entries": rows,
                                "source_title": "Internal estimate", "source_verified_at": "2026-10-21"})
    assert est.status_code == 201 and est.json()["data"]["source_verified_at"] == "2026-10-21"
    detail = _take(ctx, test, _correct(vq, 1))
    sec = _by_component(detail)
    assert (sec["gre_verbal"]["scaled_score"], sec["gre_verbal"]["score_basis"]) == (150.0, "estimate")
    assert sec["gre_verbal"]["source"]["title"] == "Internal estimate"
    assert sec["gre_quantitative"]["scaled_status"] == "no_conversion_table" and sec["gre_quantitative"]["score_basis"] is None
    assert (detail["overall_status"], detail["overall_basis"], detail["overall_score_lower"]) == ("not_reported", None, None)


# --- stability -----------------------------------------------------------------------------

def test_finalized_results_never_change_when_tables_or_sources_change(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx)
    assert _table(ctx, rw["id"], _official(_range_rows(3, 200, 20))).status_code == 201
    assert _table(ctx, math["id"], _official(_range_rows(3, 300, 0))).status_code == 201
    first = _take(ctx, test, {**_correct(qs["rw"], 1), **_correct(qs["m"], 1)})

    # A new version of the RW table (still the same form) affects new results only.
    assert _table(ctx, rw["id"], _official(_range_rows(3, 400, 20))).status_code == 201
    second = _take(ctx, test, {**_correct(qs["rw"], 1), **_correct(qs["m"], 1)})
    again = ctx.client.get(f"{API}/results/{first['id']}", headers=ctx.sh).json()["data"]
    assert again == first
    assert _by_component(second)["sat_reading_writing"]["scaled_score_lower"] == 420.0
    assert _by_component(second)["sat_reading_writing"]["conversion_table_version"] == 2

    # A result created before Task 7 (no provenance stored) is shown as is —
    # no basis or source is retro-fitted onto it.
    row = pg_session.query(ResultSection).filter(ResultSection.result_id == uuid.UUID(first["id"]),
                                                 ResultSection.score_component == "sat_math").one()
    row.score_basis = row.scaled_score_lower = row.scaled_score_upper = None
    res = pg_session.get(Result, uuid.UUID(first["id"]))
    res.overall_basis = None
    pg_session.commit()
    legacy = ctx.client.get(f"{API}/results/{first['id']}", headers=ctx.sh).json()["data"]
    m = _by_component(legacy)["sat_math"]
    assert (m["scaled_score"], m["score_basis"], m["source"], legacy["overall_basis"]) == (320.0, None, None, None)


def test_plain_and_ordinary_tests_have_no_provenance(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session, status="published")
    pg_session.commit()
    sec = _section(ctx, test, "Part 1", 0)
    qs = _questions(pg_session, test.id, uuid.UUID(sec["id"]), 2)
    pg_session.commit()
    detail = _take(ctx, test, _correct(qs, 1))
    assert detail["percentage"] == 50.0
    assert (detail["overall_basis"], detail["overall_score_lower"], detail["overall_score_upper"]) == (None, None, None)
    assert detail["sections"][0]["score_basis"] is None and detail["sections"][0]["source"] is None
