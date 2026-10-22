"""
Task 4 — exam-specific scaled scoring (IELTS/SAT/GRE), against real
PostgreSQL (migration 0025 applied by conftest).

All conversion tables here are synthetic test data, not official tables.
Everything goes through the real HTTP API with real logins.
"""
import uuid

import pytest

from app.core.security.password_service import PasswordService
from app.modules.questions.models import Question, QuestionOption
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, ScoreConversionTable, Test
from app.modules.users.models import User, UserStatus

PASSWORD = "Integration-T3st-P@ss1"
API = "/api/v1"


# --- helpers -----------------------------------------------------------------------

def _user(pg_session, role_name="Student") -> User:
    role = pg_session.query(Role).filter(Role.name == role_name).one()
    u = User(role_id=role.id, first_name="Scale", last_name=role_name,
             email=f"scale-{role_name.lower().replace(' ', '-')}-{uuid.uuid4()}@example.com",
             password_hash=PasswordService().hash_password(PASSWORD), status=UserStatus.ACTIVE)
    pg_session.add(u)
    pg_session.flush()
    return u


def _headers(client, user) -> dict:
    r = client.post(f"{API}/auth/login", json={"identifier": user.email, "password": PASSWORD})
    assert r.status_code == 200, r.json()
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


class Ctx:
    """Admin + student logged in once per test (login is rate-limited per IP)."""

    def __init__(self, client, pg_session):
        self.client, self.db = client, pg_session
        self.admin, self.student = _user(pg_session, "Admin"), _user(pg_session)
        pg_session.commit()
        self.ah, self.sh = _headers(client, self.admin), _headers(client, self.student)


def _test(pg_session, status="draft") -> Test:
    s = Subject(name=f"Scale S-{uuid.uuid4()}")
    pg_session.add(s)
    pg_session.flush()
    t = Test(subject_id=s.id, title="Practice form A", duration=120, question_count=0, status=status,
             shuffle_questions=False, shuffle_answers=False, max_attempts=5)
    pg_session.add(t)
    pg_session.flush()
    return t


def _questions(pg_session, test_id, section_id, n, module_id=None, qtype="single_choice") -> list[Question]:
    out = []
    for i in range(n):
        q = Question(test_id=test_id, section_id=section_id, module_id=module_id, question_text=f"Q{i}",
                     question_type=qtype, score=1)
        pg_session.add(q)
        pg_session.flush()
        if qtype == "single_choice":
            pg_session.add_all([QuestionOption(question_id=q.id, option_text="right", is_correct=True),
                                QuestionOption(question_id=q.id, option_text="wrong", is_correct=False)])
            pg_session.flush()
        pg_session.refresh(q)
        out.append(q)
    return out


def _set_profile(ctx, test, profile):
    return ctx.client.put(f"{API}/tests/{test.id}/scoring-profile", json={"scoring_profile": profile}, headers=ctx.ah)


def _section(ctx, test, name, order, component=None):
    body = {"test_id": str(test.id), "name": name, "order_number": order}
    if component:
        body["score_component"] = component
    r = ctx.client.post(f"{API}/tests/exam-sections", json=body, headers=ctx.ah)
    assert r.status_code == 201, r.json()
    return r.json()["data"]


def _publish_table(ctx, section_id, rows, method="exact", variant=None, headers=None):
    body = {"method": method, "entries": [{"raw": r, "scaled": s} for r, s in rows]}
    if variant:
        body["routing_variant"] = variant
    return ctx.client.post(f"{API}/tests/exam-sections/{section_id}/conversion-tables", json=body, headers=headers or ctx.ah)


def _exact(n, start, step):
    return [(i, start + i * step) for i in range(n + 1)]


def _take(ctx, test, answers: dict, headers=None):
    """Starts an attempt, answers {question: correct?}, submits, creates the
    Result and returns the result detail."""
    h = headers or ctx.sh
    attempt = ctx.client.post(f"{API}/attempts/start", json={"test_id": str(test.id)}, headers=h)
    assert attempt.status_code == 201, attempt.json()
    attempt_id = attempt.json()["data"]["id"]
    for q, value in answers.items():
        if q.question_type == "single_choice":
            opt = next(o.id for o in q.options if o.is_correct is value)
            body = {"question_id": str(q.id), "selected_option": str(opt)}
        else:
            body = {"question_id": str(q.id), "text_answer": value}
        assert ctx.client.patch(f"{API}/attempts/{attempt_id}/answer", json=body, headers=h).status_code == 200
    assert ctx.client.post(f"{API}/attempts/{attempt_id}/submit", headers=h).status_code == 200
    created = ctx.client.post(f"{API}/results", json={"attempt_id": attempt_id}, headers=h)
    assert created.status_code == 201, created.json()
    detail = ctx.client.get(f"{API}/results/{created.json()['data']['id']}", headers=h)
    assert detail.status_code == 200
    return detail.json()["data"]


def _by_component(detail):
    return {s["score_component"]: s for s in detail["sections"]}


# --- admin configuration -------------------------------------------------------------

def test_admin_sets_and_clears_scoring_profile(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    r = _set_profile(ctx, test, "sat")
    assert r.status_code == 200 and r.json()["data"]["scoring_profile"] == "sat"
    # Task 10.1 — the test is a draft, so it is read as staff (anonymous now gets 404).
    assert client.get(f"{API}/tests/{test.id}", headers=ctx.ah).json()["data"]["scoring_profile"] == "sat"
    assert _set_profile(ctx, test, None).json()["data"]["scoring_profile"] is None
    assert _set_profile(ctx, test, "toefl").status_code == 422


@pytest.mark.parametrize("role", ["Teacher", "Student", "Moderator"])
def test_non_admins_cannot_touch_scoring_configuration(client, pg_session, role):
    ctx = Ctx(client, pg_session)
    other = _user(pg_session, role)
    test = _test(pg_session)
    pg_session.commit()
    _set_profile(ctx, test, "sat")
    section = _section(ctx, test, "Math", 0, "sat_math")
    assert _publish_table(ctx, section["id"], _exact(2, 200, 10)).status_code == 201
    h = _headers(client, other)
    assert client.put(f"{API}/tests/{test.id}/scoring-profile", json={"scoring_profile": "gre"}, headers=h).status_code == 403
    assert client.get(f"{API}/tests/exam-sections/{section['id']}/conversion-tables", headers=h).status_code == 403
    assert _publish_table(ctx, section["id"], _exact(2, 200, 10), headers=h).status_code == 403


def test_unauthenticated_scoring_endpoints_are_401(client, pg_session):
    sid, tid = uuid.uuid4(), uuid.uuid4()
    assert client.put(f"{API}/tests/{tid}/scoring-profile", json={"scoring_profile": "sat"}).status_code == 401
    assert client.get(f"{API}/tests/exam-sections/{sid}/conversion-tables").status_code == 401


def test_section_component_rules(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    base = {"test_id": str(test.id), "name": "X"}
    # No profile yet.
    r = client.post(f"{API}/tests/exam-sections", json={**base, "order_number": 0, "score_component": "sat_math"}, headers=ctx.ah)
    assert r.status_code == 422
    _set_profile(ctx, test, "sat")
    # Component of another profile / unknown component.
    for comp in ("gre_verbal", "sat_physics"):
        r = client.post(f"{API}/tests/exam-sections", json={**base, "order_number": 0, "score_component": comp}, headers=ctx.ah)
        assert r.status_code == 422, comp
    math = _section(ctx, test, "Math", 0, "sat_math")
    # Duplicate component in the same test.
    r = client.post(f"{API}/tests/exam-sections", json={**base, "order_number": 1, "score_component": "sat_math"}, headers=ctx.ah)
    assert r.status_code == 422
    # Profile change while a section still carries a SAT component.
    assert _set_profile(ctx, test, "gre").status_code == 409
    # Component change after a table exists.
    assert _publish_table(ctx, math["id"], _exact(1, 200, 10)).status_code == 201
    r = client.patch(f"{API}/tests/exam-sections/{math['id']}", json={"score_component": "sat_reading_writing"}, headers=ctx.ah)
    assert r.status_code == 409
    # Unrelated edits still work.
    r = client.patch(f"{API}/tests/exam-sections/{math['id']}", json={"name": "Math (calculator)"}, headers=ctx.ah)
    assert r.status_code == 200 and r.json()["data"]["score_component"] == "sat_math"


def test_tables_are_versioned_and_listed(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    _set_profile(ctx, test, "gre")
    section = _section(ctx, test, "Verbal", 0, "gre_verbal")

    v1 = _publish_table(ctx, section["id"], [(0, 130), (2, 150), (4, 170)], method="linear")
    assert v1.status_code == 201, v1.json()
    assert (v1.json()["data"]["version"], v1.json()["data"]["is_current"]) == (1, True)
    assert v1.json()["data"]["entries"][1] == {"raw": "2", "scaled": "150"}
    v2 = _publish_table(ctx, section["id"], [(0, 130), (4, 170)], method="linear")
    assert v2.json()["data"]["version"] == 2

    listed = client.get(f"{API}/tests/exam-sections/{section['id']}/conversion-tables", headers=ctx.ah).json()["data"]
    assert [(t["version"], t["is_current"]) for t in listed] == [(2, True), (1, False)]


@pytest.mark.parametrize("rows, method", [
    ([(0, 200), (1, 199)], "exact"),          # below range + non-monotonic
    ([(0, 200), (1, 205)], "exact"),          # off the 10-point step
    ([(0, 200), (2, 220)], "exact"),          # missing raw 1
    ([(0, 200), (0, 210)], "linear"),         # duplicate raw
    ([(0, 300), (5, 250)], "linear"),         # non-monotonic
    ([(0, 200)], "linear"),                   # single point
    ([(0, 200), (1, 900)], "exact"),          # above range
])
def test_invalid_tables_rejected(client, pg_session, rows, method):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    _set_profile(ctx, test, "sat")
    section = _section(ctx, test, "Math", 0, "sat_math")
    r = _publish_table(ctx, section["id"], rows, method=method)
    assert r.status_code == 422, r.json()
    assert pg_session.query(ScoreConversionTable).filter_by(section_id=uuid.UUID(section["id"])).count() == 0


def test_table_rejected_for_writing_section_unknown_variant_and_missing_component(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    _set_profile(ctx, test, "ielts")
    writing = _section(ctx, test, "Writing", 0, "ielts_writing")
    plain = _section(ctx, test, "Warm-up", 1)
    listening = _section(ctx, test, "Listening", 2, "ielts_listening")
    assert _publish_table(ctx, writing["id"], [(0, 0), (1, 1)]).status_code == 422
    assert _publish_table(ctx, plain["id"], [(0, 0), (1, 1)]).status_code == 422
    assert _publish_table(ctx, listening["id"], [(0, 0), (1, 1)], variant="hard").status_code == 422
    assert _publish_table(ctx, str(uuid.uuid4()), [(0, 0), (1, 1)]).status_code == 404


# --- scoring end to end -----------------------------------------------------------------

def test_plain_percentage_test_is_unchanged(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session, status="published")
    section = ExamSection(test_id=test.id, name="Mechanics", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    qs = _questions(pg_session, test.id, section.id, 4)
    pg_session.commit()

    detail = _take(ctx, test, {qs[0]: True, qs[1]: True, qs[2]: True, qs[3]: False})
    assert detail["percentage"] == 75.0
    assert (detail["scoring_profile"], detail["overall_scaled_score"], detail["overall_status"]) == (None, None, None)
    assert detail["sections"] == [{
        "id": detail["sections"][0]["id"], "section_id": str(section.id), "name": "Mechanics", "order_number": 0,
        "raw_score": 3.0, "scaled_score": None, "score_component": None, "scaled_status": None, "conversion_table_version": None,
        "is_provisional": False,  # Task 5 — additive
        # Task 7 — additive provenance fields, all null for a plain test.
        "score_basis": None, "scaled_score_lower": None, "scaled_score_upper": None, "source": None,
    }]


def _sat_test(ctx, pg_session):
    test = _test(pg_session)
    pg_session.commit()
    assert _set_profile(ctx, test, "sat").status_code == 200
    rw = _section(ctx, test, "Reading and Writing", 0, "sat_reading_writing")
    math = _section(ctx, test, "Math", 1, "sat_math")
    rw_qs = _questions(pg_session, test.id, uuid.UUID(rw["id"]), 4)
    math_qs = _questions(pg_session, test.id, uuid.UUID(math["id"]), 3)
    assert _publish_table(ctx, rw["id"], _exact(4, 400, 50)).status_code == 201      # 0..4 -> 400..600
    assert _publish_table(ctx, math["id"], [(0, 200), (3, 800)], method="linear").status_code == 201
    test.status = "published"
    pg_session.commit()
    return test, rw, math, rw_qs, math_qs


def test_sat_sections_and_total(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, rw_qs, math_qs = _sat_test(ctx, pg_session)
    answers = {rw_qs[0]: True, rw_qs[1]: True, rw_qs[2]: True, rw_qs[3]: False,
               math_qs[0]: True, math_qs[1]: True, math_qs[2]: False}
    detail = _take(ctx, test, answers)

    sections = _by_component(detail)
    assert sections["sat_reading_writing"]["raw_score"] == 3.0
    assert sections["sat_reading_writing"]["scaled_score"] == 550.0        # exact: raw 3 -> 400 + 3*50
    assert sections["sat_math"]["scaled_score"] == 600.0                   # linear: 200 + 600*2/3 = 600
    assert {s["scaled_status"] for s in detail["sections"]} == {"scaled"}
    assert {s["conversion_table_version"] for s in detail["sections"]} == {1}
    assert (detail["scoring_profile"], detail["overall_scaled_score"], detail["overall_status"]) == ("sat", 1150.0, "scaled")
    for s in detail["sections"]:
        assert 200 <= s["scaled_score"] <= 800
    # The student never sees the conversion table data.
    assert "entries" not in str(detail)


def test_results_reproducible_after_table_update(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, rw_qs, math_qs = _sat_test(ctx, pg_session)
    answers = {rw_qs[0]: True, rw_qs[1]: True, math_qs[0]: True}
    before = _take(ctx, test, answers)

    assert _publish_table(ctx, rw["id"], _exact(4, 500, 50)).json()["data"]["version"] == 2

    refetched = client.get(f"{API}/results/{before['id']}", headers=ctx.sh).json()["data"]
    assert _by_component(refetched)["sat_reading_writing"]["scaled_score"] == 500.0
    assert _by_component(refetched)["sat_reading_writing"]["conversion_table_version"] == 1
    assert refetched["overall_scaled_score"] == before["overall_scaled_score"]

    after = _take(ctx, test, answers)  # a second attempt, scored with v2
    assert _by_component(after)["sat_reading_writing"]["scaled_score"] == 600.0
    assert _by_component(after)["sat_reading_writing"]["conversion_table_version"] == 2


def test_gre_verbal_quant_and_separate_awa(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    _set_profile(ctx, test, "gre")
    verbal = _section(ctx, test, "Verbal", 0, "gre_verbal")
    quant = _section(ctx, test, "Quant", 1, "gre_quantitative")
    awa = _section(ctx, test, "Analytical Writing", 2, "gre_analytical_writing")
    v_qs = _questions(pg_session, test.id, uuid.UUID(verbal["id"]), 2)
    q_qs = _questions(pg_session, test.id, uuid.UUID(quant["id"]), 2)
    essay = _questions(pg_session, test.id, uuid.UUID(awa["id"]), 1, qtype="essay")
    _publish_table(ctx, verbal["id"], _exact(2, 130, 20))
    _publish_table(ctx, quant["id"], [(0, 130), (2, 170)], method="linear")
    test.status = "published"
    pg_session.commit()

    detail = _take(ctx, test, {v_qs[0]: True, v_qs[1]: True, q_qs[0]: True, q_qs[1]: False, essay[0]: "An argument..."})
    s = _by_component(detail)
    assert s["gre_verbal"]["scaled_score"] == 170.0
    assert s["gre_quantitative"]["scaled_score"] == 150.0
    assert (s["gre_analytical_writing"]["scaled_score"], s["gre_analytical_writing"]["scaled_status"]) == (None, "pending_manual_grading")
    assert (detail["overall_scaled_score"], detail["overall_status"]) == (None, "not_reported")


def test_ielts_listening_reading_scaled_overall_pending(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    _set_profile(ctx, test, "ielts")
    listening = _section(ctx, test, "Listening", 0, "ielts_listening")
    reading = _section(ctx, test, "Reading", 1, "ielts_reading")
    writing = _section(ctx, test, "Writing", 2, "ielts_writing")
    l_qs = _questions(pg_session, test.id, uuid.UUID(listening["id"]), 4)
    r_qs = _questions(pg_session, test.id, uuid.UUID(reading["id"]), 4)
    w_qs = _questions(pg_session, test.id, uuid.UUID(writing["id"]), 1, qtype="essay")
    _publish_table(ctx, listening["id"], [(0, 0), (1, 2.5), (2, 4.5), (3, 6), (4, 7.5)])
    _publish_table(ctx, reading["id"], [(0, 2), (4, 8)], method="linear")
    test.status = "published"
    pg_session.commit()

    detail = _take(ctx, test, {l_qs[0]: True, l_qs[1]: True, l_qs[2]: True, l_qs[3]: False,
                               r_qs[0]: True, r_qs[1]: False, r_qs[2]: False, r_qs[3]: False, w_qs[0]: "Essay"})
    s = _by_component(detail)
    assert s["ielts_listening"]["scaled_score"] == 6.0
    assert s["ielts_reading"]["scaled_score"] == 3.5          # 2 + 6*1/4 = 3.5
    assert s["ielts_writing"]["scaled_status"] == "pending_manual_grading"
    for sec in (s["ielts_listening"], s["ielts_reading"]):
        assert 0 <= sec["scaled_score"] <= 9 and (sec["scaled_score"] * 2).is_integer()
    # Writing pending and Speaking absent: no overall band is invented.
    assert (detail["overall_scaled_score"], detail["overall_status"]) == (None, "pending")


def test_missing_table_out_of_range_no_component_and_ungraded_answers(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    _set_profile(ctx, test, "sat")
    rw = _section(ctx, test, "Reading and Writing", 0, "sat_reading_writing")
    math = _section(ctx, test, "Math", 1, "sat_math")
    extra = _section(ctx, test, "Unscored warm-up", 2)
    rw_qs = _questions(pg_session, test.id, uuid.UUID(rw["id"]), 3)
    math_qs = _questions(pg_session, test.id, uuid.UUID(math["id"]), 2)
    manual = _questions(pg_session, test.id, uuid.UUID(math["id"]), 1, qtype="short_answer")  # not auto-gradable
    extra_qs = _questions(pg_session, test.id, uuid.UUID(extra["id"]), 1)
    _publish_table(ctx, rw["id"], _exact(1, 200, 10))  # covers raw 0..1 only
    # Math has NO table at all.
    test.status = "published"
    pg_session.commit()

    detail = _take(ctx, test, {rw_qs[0]: True, rw_qs[1]: True, rw_qs[2]: True, math_qs[0]: True,
                               manual[0]: "42", extra_qs[0]: True})
    s = {sec["name"]: sec for sec in detail["sections"]}
    assert (s["Reading and Writing"]["scaled_score"], s["Reading and Writing"]["scaled_status"]) == (None, "raw_out_of_range")
    assert s["Reading and Writing"]["conversion_table_version"] == 1
    assert s["Math"]["scaled_status"] == "pending_manual_grading"   # delivered short_answer awaits grading
    assert s["Unscored warm-up"]["scaled_status"] == "no_score_component"
    assert (detail["overall_scaled_score"], detail["overall_status"]) == (None, "pending")


def test_section_without_table_reports_no_conversion_table(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    _set_profile(ctx, test, "gre")
    verbal = _section(ctx, test, "Verbal", 0, "gre_verbal")
    qs = _questions(pg_session, test.id, uuid.UUID(verbal["id"]), 1)
    test.status = "published"
    pg_session.commit()
    detail = _take(ctx, test, {qs[0]: True})
    assert _by_component(detail)["gre_verbal"]["scaled_status"] == "no_conversion_table"
    assert _by_component(detail)["gre_verbal"]["scaled_score"] is None


def test_adaptive_section_uses_variant_specific_table_only(client, pg_session):
    """SAT-style section with a routed second module: the variant-agnostic
    table is NOT used for a 'hard' route; only the 'hard' table is."""
    ctx = Ctx(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    _set_profile(ctx, test, "sat")
    math = _section(ctx, test, "Math", 0, "sat_math")
    section_id = uuid.UUID(math["id"])
    m1 = ExamModule(section_id=section_id, name="Module 1", order_number=0)
    m2 = ExamModule(section_id=section_id, name="Module 2 (hard)", order_number=1, routing_group="m2", routing_variant="hard")
    pg_session.add_all([m1, m2])
    pg_session.flush()
    q1 = _questions(pg_session, test.id, section_id, 1, module_id=m1.id)
    q2 = _questions(pg_session, test.id, section_id, 1, module_id=m2.id)
    pg_session.commit()
    assert _publish_table(ctx, math["id"], _exact(2, 200, 10)).status_code == 201
    test.status = "published"
    pg_session.commit()

    def run(headers):
        attempt_id = client.post(f"{API}/attempts/start", json={"test_id": str(test.id)}, headers=headers).json()["data"]["id"]
        for q, module in ((q1[0], m1), (q2[0], m2)):
            opt = next(o.id for o in q.options if o.is_correct)
            assert client.patch(f"{API}/attempts/{attempt_id}/answer", json={"question_id": str(q.id), "selected_option": str(opt)}, headers=headers).status_code == 200
            assert client.post(f"{API}/attempts/{attempt_id}/modules/{module.id}/submit", headers=headers).status_code == 200
        rid = client.post(f"{API}/results", json={"attempt_id": attempt_id}, headers=headers).json()["data"]["id"]
        return _by_component(client.get(f"{API}/results/{rid}", headers=headers).json()["data"])["sat_math"]

    assert run(ctx.sh)["scaled_status"] == "no_conversion_table"
    assert _publish_table(ctx, math["id"], _exact(2, 300, 50), variant="hard").status_code == 201
    hard = run(ctx.sh)
    assert (hard["raw_score"], hard["scaled_score"], hard["scaled_status"]) == (2.0, 400.0, "scaled")


def test_students_only_see_their_own_results(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, rw_qs, math_qs = _sat_test(ctx, pg_session)
    detail = _take(ctx, test, {rw_qs[0]: True})
    other = _headers(client, _user(pg_session))
    assert client.get(f"{API}/results/{detail['id']}", headers=other).status_code == 404
