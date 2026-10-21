"""
Task 5 — manual grading workflow (IELTS Writing/Speaking, GRE AWA), against
real PostgreSQL with migration 0026 applied (incl. the GRADE_SUBMISSIONS
permission granted to Admin and Super Admin). Everything goes through the
real HTTP API with real logins. Rubrics and tables are synthetic.
"""
import uuid

import pytest

from app.core.security.password_service import PasswordService
from app.modules.grading.models import ManualReview
from app.modules.permissions.models import Permission, RolePermission
from app.modules.questions.models import Question, QuestionOption
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamSection, Test
from app.modules.users.models import User, UserStatus

PASSWORD = "Integration-T3st-P@ss1"
API = "/api/v1"
G = f"{API}/grading"


def _user(db, role="Student") -> User:
    r = db.query(Role).filter(Role.name == role).one()
    u = User(role_id=r.id, first_name="Grade", last_name=role, email=f"grade-{role.lower().replace(' ', '-')}-{uuid.uuid4()}@example.com",
             password_hash=PasswordService().hash_password(PASSWORD), status=UserStatus.ACTIVE)
    db.add(u)
    db.flush()
    return u


def _login(client, user) -> dict:
    r = client.post(f"{API}/auth/login", json={"identifier": user.email, "password": PASSWORD})
    assert r.status_code == 200, r.json()
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _grant(db, role_name: str):
    role = db.query(Role).filter(Role.name == role_name).one()
    perm = db.query(Permission).filter(Permission.code == "GRADE_SUBMISSIONS").one()
    db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.flush()


def _questions(db, test, section, n, qtype="single_choice", score=1, texts=None):
    out = []
    for i in range(n):
        q = Question(test_id=test.id, section_id=section.id, question_text=(texts or [f"Q{i}"] * n)[i],
                     question_type=qtype, score=score if not isinstance(score, list) else score[i])
        db.add(q)
        db.flush()
        if qtype == "single_choice":
            db.add_all([QuestionOption(question_id=q.id, option_text="right", is_correct=True),
                        QuestionOption(question_id=q.id, option_text="wrong", is_correct=False)])
            db.flush()
        db.refresh(q)
        out.append(q)
    return out


RUBRIC_IELTS = [
    {"key": "task", "label": "Task response", "min": 0, "max": 9, "step": 1},
    {"key": "coherence", "label": "Coherence", "min": 0, "max": 9, "step": 1},
    {"key": "lexis", "label": "Lexical resource", "min": 0, "max": 9, "step": 1},
    {"key": "grammar", "label": "Grammar", "min": 0, "max": 9, "step": 1},
]


class Ctx:
    def __init__(self, client, db):
        self.client, self.db = client, db
        self.admin, self.student = _user(db, "Admin"), _user(db)
        db.commit()
        self.ah, self.sh = _login(client, self.admin), _login(client, self.student)

    def rubric(self, component, criteria, validated=False, rounding="half_up", headers=None):
        return self.client.post(f"{G}/rubrics", json={"score_component": component, "name": f"{component} rubric",
                                                      "criteria": criteria, "rounding": rounding, "is_validated": validated},
                                headers=headers or self.ah)

    def ielts(self):
        """IELTS form: Listening + Reading (tables), Writing (Task 1 weight 1,
        Task 2 weight 2), Speaking (one response)."""
        test = Test(subject_id=self._subject(), title="IELTS practice", duration=180, question_count=0, status="draft",
                    shuffle_questions=False, shuffle_answers=False, scoring_profile="ielts")
        self.db.add(test)
        self.db.flush()
        secs = {}
        for i, (name, comp) in enumerate([("Listening", "ielts_listening"), ("Reading", "ielts_reading"),
                                          ("Writing", "ielts_writing"), ("Speaking", "ielts_speaking")]):
            s = ExamSection(test_id=test.id, name=name, order_number=i, score_component=comp)
            self.db.add(s)
            self.db.flush()
            secs[comp] = s
        lis = _questions(self.db, test, secs["ielts_listening"], 2)
        rea = _questions(self.db, test, secs["ielts_reading"], 2)
        wri = _questions(self.db, test, secs["ielts_writing"], 2, "essay", [1, 2], ["Task 1: describe the chart", "Task 2: discuss"])
        spk = _questions(self.db, test, secs["ielts_speaking"], 1, "essay", 1, ["Speaking: talk about your town"])
        self.db.commit()
        for comp in ("ielts_listening", "ielts_reading"):
            r = self.client.post(f"{API}/tests/exam-sections/{secs[comp].id}/conversion-tables",
                                 json={"method": "exact", "entries": [{"raw": 0, "scaled": 4}, {"raw": 1, "scaled": 6}, {"raw": 2, "scaled": 7}]},
                                 headers=self.ah)
            assert r.status_code == 201, r.json()
        test.status = "published"
        self.db.commit()
        return test, secs, lis, rea, wri, spk

    def _subject(self):
        s = Subject(name=f"Grading S-{uuid.uuid4()}")
        self.db.add(s)
        self.db.flush()
        return s.id

    def take(self, test, choice_qs, text_answers: dict, headers=None, create_result=True):
        h = headers or self.sh
        attempt_id = self.client.post(f"{API}/attempts/start", json={"test_id": str(test.id)}, headers=h).json()["data"]["id"]
        for q in choice_qs:
            opt = next(o.id for o in q.options if o.is_correct)
            assert self.client.patch(f"{API}/attempts/{attempt_id}/answer", json={"question_id": str(q.id), "selected_option": str(opt)}, headers=h).status_code == 200
        for q, text in text_answers.items():
            assert self.client.patch(f"{API}/attempts/{attempt_id}/answer", json={"question_id": str(q.id), "text_answer": text}, headers=h).status_code == 200
        assert self.client.post(f"{API}/attempts/{attempt_id}/submit", headers=h).status_code == 200
        result_id = None
        if create_result:
            r = self.client.post(f"{API}/results", json={"attempt_id": attempt_id}, headers=h)
            assert r.status_code == 201, r.json()
            result_id = r.json()["data"]["id"]
        return attempt_id, result_id

    def result(self, result_id, headers=None):
        r = self.client.get(f"{API}/results/{result_id}", headers=headers or self.sh)
        assert r.status_code == 200, r.json()
        return r.json()["data"]

    def item(self, attempt_id, q):
        return f"{G}/submissions/{attempt_id}/{q.id}"

    def grade(self, attempt_id, q, scores, feedback="Good work", notes="internal", headers=None):
        h = headers or self.ah
        d = self.client.put(f"{self.item(attempt_id, q)}/draft", json={"criterion_scores": scores, "feedback": feedback, "internal_notes": notes}, headers=h)
        assert d.status_code == 200, d.json()
        f = self.client.post(f"{self.item(attempt_id, q)}/finalize", headers=h)
        assert f.status_code == 200, f.json()
        return f.json()["data"]


ALL6 = {"task": 6, "coherence": 6, "lexis": 6, "grammar": 6}
ALL7 = {"task": 7, "coherence": 7, "lexis": 7, "grammar": 7}


def _sections(detail):
    return {s["score_component"]: s for s in detail["sections"]}


# --- rubrics ---------------------------------------------------------------------------

def test_admin_publishes_rubric_versions(client, pg_session):
    ctx = Ctx(client, pg_session)
    v1 = ctx.rubric("ielts_writing", RUBRIC_IELTS)
    assert v1.status_code == 201, v1.json()
    assert (v1.json()["data"]["version"], v1.json()["data"]["is_validated"]) == (1, False)
    v2 = ctx.rubric("ielts_writing", RUBRIC_IELTS, validated=True)
    assert v2.json()["data"]["version"] == 2
    listed = client.get(f"{G}/rubrics", params={"score_component": "ielts_writing"}, headers=ctx.ah).json()["data"]
    assert [(r["version"], r["is_current"]) for r in listed[:2]] == [(2, True), (1, False)]


@pytest.mark.parametrize("component, criteria", [
    ("ielts_listening", RUBRIC_IELTS),
    ("ielts_writing", [{"key": "task", "label": "T", "min": 0, "max": 10, "step": 1}]),
    ("ielts_writing", []),
    ("gre_analytical_writing", [{"key": "a", "label": "A", "min": 0, "max": 9, "step": 1}]),
])
def test_invalid_rubrics_are_422(client, pg_session, component, criteria):
    ctx = Ctx(client, pg_session)
    assert ctx.rubric(component, criteria).status_code == 422


def test_rubric_permissions(client, pg_session):
    ctx = Ctx(client, pg_session)
    teacher = _user(pg_session, "Teacher")
    _grant(pg_session, "Teacher")
    pg_session.commit()
    th = _login(client, teacher)
    # A grader may read rubrics but not publish them; a student may do neither.
    assert client.get(f"{G}/rubrics", headers=th).status_code == 200
    assert ctx.rubric("ielts_writing", RUBRIC_IELTS, headers=th).status_code == 403
    assert client.get(f"{G}/rubrics", headers=ctx.sh).status_code == 403
    assert client.get(f"{G}/rubrics").status_code == 401


# --- full IELTS workflow ---------------------------------------------------------------

def test_ielts_draft_finalize_partial_and_overall(client, pg_session):
    ctx = Ctx(client, pg_session)
    assert ctx.rubric("ielts_writing", RUBRIC_IELTS).status_code == 201
    assert ctx.rubric("ielts_speaking", RUBRIC_IELTS).status_code == 201
    test, secs, lis, rea, wri, spk = ctx.ielts()
    attempt_id, result_id = ctx.take(test, lis + rea[:1], {wri[0]: "Chart essay", wri[1]: "Opinion essay", spk[0]: "Transcript"})

    before = ctx.result(result_id)
    s = _sections(before)
    assert (s["ielts_listening"]["scaled_score"], s["ielts_reading"]["scaled_score"]) == (7.0, 6.0)
    assert s["ielts_writing"]["scaled_status"] == "pending_manual_grading"
    assert s["ielts_speaking"]["scaled_status"] == "pending_manual_grading"
    assert (before["overall_scaled_score"], before["overall_status"]) == (None, "pending")
    percentage_before = before["percentage"]

    # Queue lists the three manual items as pending.
    queue = client.get(f"{G}/submissions", params={"test_id": str(test.id)}, headers=ctx.ah).json()["data"]
    assert queue["total"] == 3 and {i["status"] for i in queue["items"]} == {"pending"}

    # Draft with partial scores, then update it.
    item = ctx.item(attempt_id, wri[0])
    d1 = client.put(f"{item}/draft", json={"criterion_scores": {"task": 6}}, headers=ctx.ah)
    assert d1.status_code == 200 and d1.json()["data"]["status"] == "draft"
    detail = client.get(item, headers=ctx.ah).json()["data"]
    assert (detail["status"], detail["response_text"], detail["rubric"]["version"]) == ("draft", "Chart essay", 1)
    # Finalizing an incomplete draft is rejected.
    assert client.post(f"{item}/finalize", headers=ctx.ah).status_code == 422
    assert client.put(f"{item}/draft", json={"criterion_scores": ALL6, "feedback": "Clear overview", "internal_notes": "check t1"}, headers=ctx.ah).status_code == 200
    final1 = client.post(f"{item}/finalize", headers=ctx.ah).json()["data"]
    assert (final1["status"], final1["reported_score"], final1["criterion_total"], final1["is_provisional"]) == ("finalized", 6.0, 24.0, True)
    assert final1["grader_id"] == str(ctx.admin.id) and final1["finalized_at"]

    s = _sections(ctx.result(result_id))
    assert (s["ielts_writing"]["scaled_status"], s["ielts_writing"]["scaled_score"]) == ("partially_graded", None)

    ctx.grade(attempt_id, wri[1], ALL7)  # Task 2, weight 2
    after_writing = ctx.result(result_id)
    s = _sections(after_writing)
    # (1*6 + 2*7) / 3 = 6.67 -> 6.5
    assert (s["ielts_writing"]["scaled_status"], s["ielts_writing"]["scaled_score"], s["ielts_writing"]["is_provisional"]) == ("scaled", 6.5, True)
    assert after_writing["overall_status"] == "pending"     # Speaking still missing

    ctx.grade(attempt_id, spk[0], {"task": 6, "coherence": 7, "lexis": 6, "grammar": 6})  # 6.25 -> 6.5
    final = ctx.result(result_id)
    # (7 + 6 + 6.5 + 6.5) / 4 = 6.5
    assert (final["overall_scaled_score"], final["overall_status"], final["is_provisional"]) == (6.5, "scaled", True)
    assert final["percentage"] == percentage_before          # automatic score untouched

    # Student sees criterion scores and feedback, never internal notes / grader / drafts.
    q = next(x for x in final["questions"] if x["question_id"] == str(wri[0].id))
    assert q["manual_grade"]["reported_score"] == 6.0 and q["manual_grade"]["feedback"] == "Clear overview"
    assert [c["score"] for c in q["manual_grade"]["criteria"]] == ["6", "6", "6", "6"]
    for leak in ("internal_notes", "check t1", "grader_id", str(ctx.admin.id)):
        assert leak not in str(final)


def test_result_created_after_grading_uses_finalized_reviews(client, pg_session):
    ctx = Ctx(client, pg_session)
    ctx.rubric("ielts_writing", RUBRIC_IELTS, validated=True)
    ctx.rubric("ielts_speaking", RUBRIC_IELTS, validated=True)
    test, secs, lis, rea, wri, spk = ctx.ielts()
    attempt_id, _ = ctx.take(test, lis + rea, {wri[0]: "a", wri[1]: "b", spk[0]: "c"}, create_result=False)
    for q in (wri[0], wri[1], spk[0]):
        ctx.grade(attempt_id, q, ALL7)
    result_id = client.post(f"{API}/results", json={"attempt_id": attempt_id}, headers=ctx.sh).json()["data"]["id"]
    detail = ctx.result(result_id)
    s = _sections(detail)
    assert s["ielts_writing"]["scaled_score"] == 7.0 and s["ielts_writing"]["is_provisional"] is False
    assert (detail["overall_scaled_score"], detail["overall_status"], detail["is_provisional"]) == (7.0, "scaled", False)


def test_unanswered_essay_can_still_be_graded(client, pg_session):
    ctx = Ctx(client, pg_session)
    ctx.rubric("ielts_writing", RUBRIC_IELTS)
    test, secs, lis, rea, wri, spk = ctx.ielts()
    attempt_id, _ = ctx.take(test, [], {wri[1]: "only task 2"})
    detail = client.get(ctx.item(attempt_id, wri[0]), headers=ctx.ah).json()["data"]
    assert detail["response_text"] is None
    assert ctx.grade(attempt_id, wri[0], {"task": 0, "coherence": 0, "lexis": 0, "grammar": 0})["reported_score"] == 0.0


# --- revisions and history -------------------------------------------------------------------

def test_revision_keeps_history_and_updates_result(client, pg_session):
    ctx = Ctx(client, pg_session)
    ctx.rubric("ielts_writing", RUBRIC_IELTS)
    test, secs, lis, rea, wri, spk = ctx.ielts()
    attempt_id, result_id = ctx.take(test, [], {wri[0]: "a", wri[1]: "b"})
    first = ctx.grade(attempt_id, wri[0], ALL6, feedback="v1")
    ctx.grade(attempt_id, wri[1], ALL6)
    assert _sections(ctx.result(result_id))["ielts_writing"]["scaled_score"] == 6.0

    item = ctx.item(attempt_id, wri[0])
    # A finalized grade can't be edited directly or re-finalized.
    assert client.put(f"{item}/draft", json={"criterion_scores": ALL7}, headers=ctx.ah).status_code == 409
    assert client.post(f"{item}/finalize", headers=ctx.ah).status_code == 409
    assert client.post(f"{item}/revise", json={"reason": ""}, headers=ctx.ah).status_code == 422

    rev = client.post(f"{item}/revise", json={"reason": "Mis-scored coherence"}, headers=ctx.ah)
    assert rev.status_code == 201, rev.json()
    rev = rev.json()["data"]
    assert (rev["status"], rev["revision_number"], rev["supersedes_id"], rev["criterion_scores"]) == ("draft", 2, first["id"], {k: "6" for k in ALL6})
    assert client.post(f"{item}/revise", json={"reason": "again"}, headers=ctx.ah).status_code == 409   # draft already open
    # The old grade still counts until the revision is finalized.
    assert _sections(ctx.result(result_id))["ielts_writing"]["scaled_score"] == 6.0

    ctx.grade(attempt_id, wri[0], {"task": 9, "coherence": 9, "lexis": 9, "grammar": 9}, feedback="v2")
    history = client.get(item, headers=ctx.ah).json()["data"]["reviews"]
    assert [(h["revision_number"], h["status"]) for h in history] == [(1, "superseded"), (2, "finalized")]
    assert history[0]["reported_score"] == 6.0 and history[1]["revision_reason"] == "Mis-scored coherence"

    detail = ctx.result(result_id)
    assert _sections(detail)["ielts_writing"]["scaled_score"] == 7.0      # (9 + 2*6)/3
    q = next(x for x in detail["questions"] if x["question_id"] == str(wri[0].id))
    assert (q["manual_grade"]["revision_number"], q["manual_grade"]["feedback"]) == (2, "v2")
    assert pg_session.query(ManualReview).filter_by(attempt_id=uuid.UUID(attempt_id), question_id=wri[0].id).count() == 2


def test_later_rubric_version_does_not_rewrite_finalized_grades(client, pg_session):
    ctx = Ctx(client, pg_session)
    ctx.rubric("ielts_writing", RUBRIC_IELTS)
    test, secs, lis, rea, wri, spk = ctx.ielts()
    attempt_id, result_id = ctx.take(test, [], {wri[0]: "a", wri[1]: "b"})
    ctx.grade(attempt_id, wri[0], ALL6)
    ctx.grade(attempt_id, wri[1], ALL6)
    before = ctx.result(result_id)

    new = ctx.rubric("ielts_writing", [{"key": "overall", "label": "Overall", "min": 0, "max": 9, "step": 1}], validated=True)
    assert new.json()["data"]["version"] == 2
    after = ctx.result(result_id)
    assert _sections(after)["ielts_writing"] == _sections(before)["ielts_writing"]
    q = next(x for x in after["questions"] if x["question_id"] == str(wri[0].id))
    assert [c["key"] for c in q["manual_grade"]["criteria"]] == ["task", "coherence", "lexis", "grammar"]
    # A revision keeps the rubric version of the grade it corrects.
    assert client.post(f"{ctx.item(attempt_id, wri[0])}/revise", json={"reason": "recheck"}, headers=ctx.ah).status_code == 201
    detail = client.get(ctx.item(attempt_id, wri[0]), headers=ctx.ah).json()["data"]
    assert detail["rubric"]["version"] == 1 and detail["rubric"]["is_current"] is False
    assert [r["rubric_version"] for r in detail["reviews"]] == [1, 1]


# --- validation and payload tampering --------------------------------------------------------

@pytest.mark.parametrize("payload", [
    {"criterion_scores": {"task": 10}},
    {"criterion_scores": {"task": 6.5}},
    {"criterion_scores": {"unknown": 5}},
    {"criterion_scores": {"task": "abc"}},
    {"criterion_scores": {"task": 6}, "grader_id": str(uuid.uuid4())},
    {"criterion_scores": {"task": 6}, "status": "finalized"},
    {"criterion_scores": {"task": 6}, "rubric_id": str(uuid.uuid4())},
    {"criterion_scores": {"task": 6}, "reported_score": 9},
    {"criterion_scores": {"task": 6}, "feedback": "x" * 5001},
])
def test_invalid_or_tampered_draft_payloads_are_422(client, pg_session, payload):
    ctx = Ctx(client, pg_session)
    ctx.rubric("ielts_writing", RUBRIC_IELTS)
    test, secs, lis, rea, wri, spk = ctx.ielts()
    attempt_id, _ = ctx.take(test, [], {wri[0]: "a"}, create_result=False)
    r = client.put(f"{ctx.item(attempt_id, wri[0])}/draft", json=payload, headers=ctx.ah)
    assert r.status_code == 422, r.json()
    assert pg_session.query(ManualReview).filter_by(attempt_id=uuid.UUID(attempt_id)).count() == 0


def test_missing_rubric_blocks_grading(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, secs, lis, rea, wri, spk = ctx.ielts()
    attempt_id, _ = ctx.take(test, [], {wri[0]: "a"}, create_result=False)
    # No rubric exists for ielts_writing in this (rolled-back) transaction.
    detail = client.get(ctx.item(attempt_id, wri[0]), headers=ctx.ah).json()["data"]
    assert detail["rubric"] is None and detail["status"] == "pending"
    r = client.put(f"{ctx.item(attempt_id, wri[0])}/draft", json={"criterion_scores": {}}, headers=ctx.ah)
    assert r.status_code == 422 and r.json()["success"] is False
    assert pg_session.query(ManualReview).filter_by(attempt_id=uuid.UUID(attempt_id)).count() == 0


def test_non_gradable_items_are_404(client, pg_session):
    ctx = Ctx(client, pg_session)
    ctx.rubric("ielts_writing", RUBRIC_IELTS)
    test, secs, lis, rea, wri, spk = ctx.ielts()
    in_progress = client.post(f"{API}/attempts/start", json={"test_id": str(test.id)}, headers=ctx.sh).json()["data"]["id"]
    assert client.get(ctx.item(in_progress, wri[0]), headers=ctx.ah).status_code == 404   # attempt not finished
    assert client.post(f"{API}/attempts/{in_progress}/submit", headers=ctx.sh).status_code == 200
    assert client.get(ctx.item(in_progress, lis[0]), headers=ctx.ah).status_code == 404   # auto-graded Listening question
    assert client.get(ctx.item(uuid.uuid4(), wri[0]), headers=ctx.ah).status_code == 404
    other_test, _, _, _, other_wri, _ = ctx.ielts()
    assert client.get(ctx.item(in_progress, other_wri[0]), headers=ctx.ah).status_code == 404  # another test's question


# --- permissions and isolation ---------------------------------------------------------------

def test_grading_requires_explicit_permission(client, pg_session):
    ctx = Ctx(client, pg_session)
    ctx.rubric("ielts_writing", RUBRIC_IELTS)
    test, secs, lis, rea, wri, spk = ctx.ielts()
    attempt_id, _ = ctx.take(test, [], {wri[0]: "essay"}, create_result=False)
    teacher, moderator = _user(pg_session, "Teacher"), _user(pg_session, "Moderator")
    pg_session.commit()
    th, mh = _login(client, teacher), _login(client, moderator)

    for h in (th, mh, ctx.sh):
        assert client.get(f"{G}/submissions", headers=h).status_code == 403
        assert client.get(ctx.item(attempt_id, wri[0]), headers=h).status_code == 403
        assert client.put(f"{ctx.item(attempt_id, wri[0])}/draft", json={"criterion_scores": ALL6}, headers=h).status_code == 403
    assert client.get(f"{G}/submissions").status_code == 401

    _grant(pg_session, "Teacher")
    pg_session.commit()
    assert client.get(f"{G}/submissions", headers=th).status_code == 200
    graded = ctx.grade(attempt_id, wri[0], ALL6, headers=th)
    assert graded["grader_id"] == str(teacher.id)


def test_drafts_belong_to_their_grader(client, pg_session):
    ctx = Ctx(client, pg_session)
    ctx.rubric("ielts_writing", RUBRIC_IELTS)
    test, secs, lis, rea, wri, spk = ctx.ielts()
    attempt_id, _ = ctx.take(test, [], {wri[0]: "essay"}, create_result=False)
    other_admin = _user(pg_session, "Admin")
    pg_session.commit()
    oh = _login(client, other_admin)
    item = ctx.item(attempt_id, wri[0])
    assert client.put(f"{item}/draft", json={"criterion_scores": ALL6}, headers=ctx.ah).status_code == 200
    assert client.put(f"{item}/draft", json={"criterion_scores": ALL7}, headers=oh).status_code == 409
    assert client.post(f"{item}/finalize", headers=oh).status_code == 409


def test_students_only_see_their_own_finalized_grades(client, pg_session):
    ctx = Ctx(client, pg_session)
    ctx.rubric("ielts_writing", RUBRIC_IELTS)
    test, secs, lis, rea, wri, spk = ctx.ielts()
    attempt_id, result_id = ctx.take(test, [], {wri[0]: "my essay", wri[1]: "my other essay"})
    # A draft is invisible to the student.
    client.put(f"{ctx.item(attempt_id, wri[0])}/draft", json={"criterion_scores": ALL6, "feedback": "draft fb"}, headers=ctx.ah)
    detail = ctx.result(result_id)
    assert all(q["manual_grade"] is None for q in detail["questions"])
    assert "draft fb" not in str(detail)
    # Another student cannot read this result.
    other = _user(pg_session)
    pg_session.commit()
    assert client.get(f"{API}/results/{result_id}", headers=_login(client, other)).status_code == 404


# --- GRE AWA and regression --------------------------------------------------------------------

def test_gre_awa_is_graded_separately_from_verbal_and_quant(client, pg_session):
    ctx = Ctx(client, pg_session)
    assert ctx.rubric("gre_analytical_writing", [{"key": "analysis", "label": "Analysis", "min": 0, "max": 6, "step": 0.5}], validated=True).status_code == 201
    test = Test(subject_id=ctx._subject(), title="GRE practice", duration=120, question_count=0, status="draft",
                shuffle_questions=False, shuffle_answers=False, scoring_profile="gre")
    pg_session.add(test)
    pg_session.flush()
    verbal = ExamSection(test_id=test.id, name="Verbal", order_number=0, score_component="gre_verbal")
    awa = ExamSection(test_id=test.id, name="Analytical Writing", order_number=1, score_component="gre_analytical_writing")
    pg_session.add_all([verbal, awa])
    pg_session.flush()
    v_qs = _questions(pg_session, test, verbal, 2)
    essay = _questions(pg_session, test, awa, 1, "essay")
    pg_session.commit()
    client.post(f"{API}/tests/exam-sections/{verbal.id}/conversion-tables",
                json={"method": "exact", "entries": [{"raw": 0, "scaled": 130}, {"raw": 1, "scaled": 150}, {"raw": 2, "scaled": 170}]}, headers=ctx.ah)
    test.status = "published"
    pg_session.commit()

    attempt_id, result_id = ctx.take(test, v_qs, {essay[0]: "An argument essay"})
    before = _sections(ctx.result(result_id))
    assert before["gre_verbal"]["scaled_score"] == 170.0
    assert before["gre_analytical_writing"]["scaled_status"] == "pending_manual_grading"

    ctx.grade(attempt_id, essay[0], {"analysis": 4.5})
    detail = ctx.result(result_id)
    s = _sections(detail)
    assert (s["gre_analytical_writing"]["scaled_score"], s["gre_analytical_writing"]["is_provisional"]) == (4.5, False)
    assert s["gre_verbal"]["scaled_score"] == 170.0
    assert (detail["overall_scaled_score"], detail["overall_status"]) == (None, "not_reported")


def test_auto_graded_results_unchanged_by_grading_module(client, pg_session):
    ctx = Ctx(client, pg_session)
    subject = ctx._subject()
    test = Test(subject_id=subject, title="Physics", duration=30, question_count=0, status="published",
                shuffle_questions=False, shuffle_answers=False)
    pg_session.add(test)
    pg_session.flush()
    section = ExamSection(test_id=test.id, name="Mechanics", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    qs = _questions(pg_session, test, section, 3)
    pg_session.commit()
    _, result_id = ctx.take(test, qs[:2], {})
    detail = ctx.result(result_id)
    assert round(detail["percentage"], 2) == 66.67
    assert (detail["scoring_profile"], detail["is_provisional"]) == (None, False)
    assert all(q["manual_grade"] is None for q in detail["questions"])
    # Plain tests never appear in the grading queue.
    queue = client.get(f"{G}/submissions", params={"test_id": str(test.id)}, headers=ctx.ah).json()["data"]
    assert queue["total"] == 0
