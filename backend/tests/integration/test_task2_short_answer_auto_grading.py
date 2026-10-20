"""
Task 2 — automatic grading of short_answer questions, against real
PostgreSQL (migration 0023 applied by conftest's alembic upgrade).

Everything goes through the real HTTP API with real logins, so routing,
role checks, schemas, the save -> submit -> result pipeline and the
database constraints are all exercised together.
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security.password_service import PasswordService
from app.modules.questions.models import Question, QuestionOption
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamSection, Test
from app.modules.users.models import User, UserStatus

PASSWORD = "Integration-T3st-P@ss1"


# --- helpers ---------------------------------------------------------------------

def _user(pg_session, role_name="Student") -> User:
    role = pg_session.query(Role).filter(Role.name == role_name).one()
    user = User(
        role_id=role.id, first_name="Grading", last_name=role_name,
        email=f"grading-{role_name.lower().replace(' ', '-')}-{uuid.uuid4()}@example.com",
        password_hash=PasswordService().hash_password(PASSWORD), status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()
    return user


def _headers(client, user) -> dict:
    r = client.post("/api/v1/auth/login", json={"identifier": user.email, "password": PASSWORD})
    assert r.status_code == 200, r.json()
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _test(pg_session, status="draft") -> Test:
    subject = Subject(name=f"Grading S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    t = Test(subject_id=subject.id, title="Grading test", duration=60, question_count=0, status=status,
             shuffle_questions=False, shuffle_answers=False)
    pg_session.add(t)
    pg_session.flush()
    return t


def _create_question(client, headers, test_id, **body):
    payload = {"test_id": str(test_id), "question_text": body.pop("question_text", "Fill the gap"),
               "question_type": body.pop("question_type", "short_answer"), **body}
    return client.post("/api/v1/questions", json=payload, headers=headers)


def _publish(pg_session, test):
    test.status = "published"
    pg_session.commit()


def _start(client, headers, test_id) -> str:
    r = client.post("/api/v1/attempts/start", json={"test_id": str(test_id)}, headers=headers)
    assert r.status_code == 201, r.json()
    return r.json()["data"]["id"]


def _save_text(client, headers, attempt_id, question_id, text):
    return client.patch(f"/api/v1/attempts/{attempt_id}/answer",
                        json={"question_id": str(question_id), "text_answer": text}, headers=headers)


def _submit(client, headers, attempt_id):
    r = client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=headers)
    assert r.status_code == 200, r.json()
    return r.json()["data"]


def _answer_is_correct(pg_session, attempt_id, question_id):
    from app.modules.attempts.models import Answer
    pg_session.expire_all()
    a = pg_session.query(Answer).filter(Answer.attempt_id == uuid.UUID(attempt_id), Answer.question_id == uuid.UUID(str(question_id))).one_or_none()
    return a


class _Actors:
    """One admin and one student, each logged in ONCE per test: the login
    endpoint is rate-limited per client IP, and conftest gives each test
    a single fake IP."""

    def __init__(self, client, pg_session):
        self.admin, self.student = _user(pg_session, "Admin"), _user(pg_session)
        pg_session.commit()
        self.ah, self.sh = _headers(client, self.admin), _headers(client, self.student)


def _grade_one(client, pg_session, config: dict, answer: str, actors: "_Actors | None" = None):
    """Creates a one-question test with `config`, answers it, submits it,
    and returns (save_response, submit_data)."""
    actors = actors or _Actors(client, pg_session)
    test = _test(pg_session)
    pg_session.commit()
    q = _create_question(client, actors.ah, test.id, **config)
    assert q.status_code == 201, q.json()
    _publish(pg_session, test)
    sh = actors.sh
    attempt_id = _start(client, sh, test.id)
    save = _save_text(client, sh, attempt_id, q.json()["data"]["id"], answer)
    return save, _submit(client, sh, attempt_id)


TEXT_CFG = {"answer_format": "text", "accepted_answers": ["library", "the library"]}
NUM_CFG = {"answer_format": "numeric", "accepted_answers": ["2/3"], "numeric_tolerance": "0.001"}


# --- admin configuration ------------------------------------------------------------

def test_admin_creates_text_and_numeric_configs_and_reads_them_back(client, pg_session):
    admin = _user(pg_session, "Admin")
    test = _test(pg_session)
    pg_session.commit()
    h = _headers(client, admin)

    text = _create_question(client, h, test.id, **TEXT_CFG)
    assert text.status_code == 201, text.json()
    d = text.json()["data"]
    assert (d["answer_format"], d["accepted_answers"], d["case_sensitive"], d["numeric_tolerance"]) == (
        "text", ["library", "the library"], False, None)

    num = _create_question(client, h, test.id, **NUM_CFG)
    assert num.status_code == 201, num.json()
    d = num.json()["data"]
    assert (d["answer_format"], d["accepted_answers"], d["numeric_tolerance"]) == ("numeric", ["2/3"], "0.001")

    fetched = client.get(f"/api/v1/questions/{num.json()['data']['id']}", headers=h)
    assert fetched.json()["data"]["numeric_tolerance"] == "0.001"


def test_teacher_can_configure_grading(client, pg_session):
    teacher = _user(pg_session, "Teacher")
    test = _test(pg_session)
    pg_session.commit()
    r = _create_question(client, _headers(client, teacher), test.id, **TEXT_CFG)
    assert r.status_code == 201, r.json()


@pytest.mark.parametrize("body", [
    {"question_type": "essay", "answer_format": "text", "accepted_answers": ["x"]},
    {"answer_format": "numeric", "accepted_answers": ["1,5"]},
    {"answer_format": "numeric", "accepted_answers": ["1"], "numeric_tolerance": "-0.5"},
    {"answer_format": "text", "accepted_answers": ["x"], "numeric_tolerance": "0.1"},
    {"answer_format": "text", "accepted_answers": []},
    {"answer_format": "regex", "accepted_answers": ["x"]},
    {"accepted_answers": ["x"]},
])
def test_invalid_configs_rejected_with_422(client, pg_session, body):
    admin = _user(pg_session, "Admin")
    test = _test(pg_session)
    pg_session.commit()
    r = _create_question(client, _headers(client, admin), test.id, **body)
    assert r.status_code == 422, r.json()
    assert r.json()["success"] is False


def test_update_validates_merged_configuration(client, pg_session):
    admin = _user(pg_session, "Admin")
    test = _test(pg_session)
    pg_session.commit()
    h = _headers(client, admin)
    qid = _create_question(client, h, test.id, **TEXT_CFG).json()["data"]["id"]

    # Tolerance alone on a stored text config -> incoherent merged state.
    assert client.patch(f"/api/v1/questions/{qid}", json={"numeric_tolerance": "0.1"}, headers=h).status_code == 422
    # Switch to numeric while the stored answers aren't numbers -> rejected.
    assert client.patch(f"/api/v1/questions/{qid}", json={"answer_format": "numeric"}, headers=h).status_code == 422
    # Switch to numeric WITH new answers -> ok.
    ok = client.patch(f"/api/v1/questions/{qid}", json={"answer_format": "numeric", "accepted_answers": ["3.5"], "numeric_tolerance": "0.05"}, headers=h)
    assert ok.status_code == 200, ok.json()
    assert ok.json()["data"]["numeric_tolerance"] == "0.05"
    # Unrelated update keeps the configuration.
    ok = client.patch(f"/api/v1/questions/{qid}", json={"difficulty": "hard"}, headers=h)
    assert ok.json()["data"]["accepted_answers"] == ["3.5"]
    # Clearing the configuration back to manual review.
    cleared = client.patch(f"/api/v1/questions/{qid}", json={"answer_format": None, "accepted_answers": None, "numeric_tolerance": None}, headers=h)
    assert cleared.status_code == 200, cleared.json()
    assert cleared.json()["data"]["answer_format"] is None


def test_student_cannot_read_or_write_question_answer_keys(client, pg_session):
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    pg_session.commit()
    qid = _create_question(client, _headers(client, admin), test.id, **TEXT_CFG).json()["data"]["id"]
    sh = _headers(client, student)

    assert client.get(f"/api/v1/questions/{qid}", headers=sh).status_code == 403
    assert client.get("/api/v1/questions", params={"test_id": str(test.id)}, headers=sh).status_code == 403
    assert client.patch(f"/api/v1/questions/{qid}", json={"accepted_answers": ["hack"]}, headers=sh).status_code == 403
    assert _create_question(client, sh, test.id, **TEXT_CFG).status_code == 403
    assert client.get(f"/api/v1/questions/{qid}").status_code == 401


def test_database_rejects_config_on_non_short_answer(pg_session):
    test = _test(pg_session)
    pg_session.add(Question(test_id=test.id, question_text="Q", question_type="essay", score=1,
                            answer_format="text", accepted_answers=["x"]))
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


def test_database_rejects_negative_or_text_tolerance(pg_session):
    test = _test(pg_session)
    pg_session.add(Question(test_id=test.id, question_text="Q", question_type="short_answer", score=1,
                            answer_format="text", accepted_answers=["x"], numeric_tolerance=Decimal("0.1")))
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


# --- the attempt payload never carries the answer key -----------------------------------

def test_attempt_payload_does_not_expose_accepted_answers(client, pg_session):
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    pg_session.commit()
    secret = f"secretanswer{uuid.uuid4().hex[:8]}"
    _create_question(client, _headers(client, admin), test.id,
                     answer_format="text", accepted_answers=[secret], case_sensitive=True)
    _publish(pg_session, test)
    sh = _headers(client, student)
    attempt_id = _start(client, sh, test.id)

    detail = client.get(f"/api/v1/attempts/{attempt_id}", headers=sh)
    assert detail.status_code == 200
    body = detail.text
    assert secret not in body
    for key in ("accepted_answers", "answer_format", "numeric_tolerance", "case_sensitive"):
        assert key not in body
    assert set(detail.json()["data"]["questions"][0]) == {
        "id", "question_text", "question_type", "score", "options", "group_id", "group_title", "stimulus_text", "media",
    }


# --- grading through the real save -> submit pipeline -----------------------------------

@pytest.mark.parametrize("answer, expected_pct", [
    ("library", 100.0), ("  LIBRARY ", 100.0), ("The   Library", 100.0), ("libary", 0.0), ("library.", 0.0),
])
def test_text_grading_end_to_end(client, pg_session, answer, expected_pct):
    save, result = _grade_one(client, pg_session, TEXT_CFG, answer)
    assert save.status_code == 200, save.json()
    assert result["percentage"] == expected_pct


def test_case_sensitive_text_grading(client, pg_session):
    cfg = {"answer_format": "text", "accepted_answers": ["NaCl"], "case_sensitive": True}
    actors = _Actors(client, pg_session)
    _, right = _grade_one(client, pg_session, cfg, "NaCl", actors)
    _, wrong = _grade_one(client, pg_session, cfg, "nacl", actors)
    assert (right["percentage"], wrong["percentage"]) == (100.0, 0.0)


@pytest.mark.parametrize("answer, expected_pct", [
    ("2/3", 100.0), (".6667", 100.0), ("0.667", 100.0), (".666", 100.0),   # within 0.001
    ("0.6656", 0.0), ("0.668", 0.0), ("4/6", 100.0), ("-2/3", 0.0),
])
def test_numeric_grading_with_tolerance_end_to_end(client, pg_session, answer, expected_pct):
    save, result = _grade_one(client, pg_session, NUM_CFG, answer)
    assert save.status_code == 200, save.json()
    assert result["percentage"] == expected_pct


def test_numeric_tolerance_boundary_is_inclusive_end_to_end(client, pg_session):
    cfg = {"answer_format": "numeric", "accepted_answers": ["10"], "numeric_tolerance": "0.5"}
    actors = _Actors(client, pg_session)
    _, at_upper = _grade_one(client, pg_session, cfg, "10.5", actors)
    _, at_lower = _grade_one(client, pg_session, cfg, "9.5", actors)
    _, beyond = _grade_one(client, pg_session, cfg, "10.5000001", actors)
    assert (at_upper["percentage"], at_lower["percentage"], beyond["percentage"]) == (100.0, 100.0, 0.0)


@pytest.mark.parametrize("bad", ["1,5", "abc", "1e3", "3/0", "1 000"])
def test_invalid_numeric_input_is_rejected_and_previous_answer_kept(client, pg_session, bad):
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    pg_session.commit()
    qid = _create_question(client, _headers(client, admin), test.id, **NUM_CFG).json()["data"]["id"]
    _publish(pg_session, test)
    sh = _headers(client, student)
    attempt_id = _start(client, sh, test.id)

    assert _save_text(client, sh, attempt_id, qid, "2/3").status_code == 200
    rejected = _save_text(client, sh, attempt_id, qid, bad)
    assert rejected.status_code == 422
    assert rejected.json()["success"] is False

    stored = _answer_is_correct(pg_session, attempt_id, qid)
    assert stored.text_answer == "2/3" and stored.is_correct is True
    assert _submit(client, sh, attempt_id)["percentage"] == 100.0


def test_empty_answer_counts_as_unanswered(client, pg_session):
    save, result = _grade_one(client, pg_session, TEXT_CFG, "   ")
    assert save.status_code == 200
    assert result["percentage"] == 0.0


# --- scoring integration and regression ---------------------------------------------------

def test_mixed_exam_scores_choice_and_configured_short_answers_only(client, pg_session):
    """single_choice (right) + multiple_choice (wrong) + true_false (right)
    + configured short_answer (right) + UNconfigured short_answer + essay.
    The last two stay ungraded and out of the denominator: 3/4 = 75%."""
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    pg_session.commit()
    h = _headers(client, admin)

    def choice(qtype, options):
        r = _create_question(client, h, test.id, question_type=qtype, options=options)
        assert r.status_code == 201, r.json()
        return r.json()["data"]

    sc = choice("single_choice", [{"option_text": "A", "is_correct": True}, {"option_text": "B", "is_correct": False}])
    mc = choice("multiple_choice", [{"option_text": "A", "is_correct": True}, {"option_text": "B", "is_correct": True}, {"option_text": "C", "is_correct": False}])
    tf = choice("true_false", [{"option_text": "Rost", "is_correct": True}, {"option_text": "Yolg'on", "is_correct": False}])
    sa = _create_question(client, h, test.id, **TEXT_CFG).json()["data"]
    manual = _create_question(client, h, test.id).json()["data"]
    essay = _create_question(client, h, test.id, question_type="essay").json()["data"]
    _publish(pg_session, test)

    sh = _headers(client, student)
    attempt_id = _start(client, sh, test.id)
    correct = lambda q: next(o["id"] for o in q["options"] if o["is_correct"])  # noqa: E731
    assert client.patch(f"/api/v1/attempts/{attempt_id}/answer", json={"question_id": sc["id"], "selected_option": correct(sc)}, headers=sh).status_code == 200
    assert client.patch(f"/api/v1/attempts/{attempt_id}/answer", json={"question_id": mc["id"], "selected_options": [mc["options"][0]["id"]]}, headers=sh).status_code == 200
    assert client.patch(f"/api/v1/attempts/{attempt_id}/answer", json={"question_id": tf["id"], "selected_option": correct(tf)}, headers=sh).status_code == 200
    assert _save_text(client, sh, attempt_id, sa["id"], "Library").status_code == 200
    assert _save_text(client, sh, attempt_id, manual["id"], "anything").status_code == 200
    assert _save_text(client, sh, attempt_id, essay["id"], "A long essay").status_code == 200

    result = _submit(client, sh, attempt_id)
    assert result["percentage"] == 75.0
    assert result["score"] == 3.0

    assert _answer_is_correct(pg_session, attempt_id, manual["id"]).is_correct is None
    assert _answer_is_correct(pg_session, attempt_id, essay["id"]).is_correct is None
    assert _answer_is_correct(pg_session, attempt_id, sa["id"]).is_correct is True


def test_section_raw_score_includes_configured_short_answers(client, pg_session):
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    section = ExamSection(test_id=test.id, name="Math", order_number=0)
    pg_session.add(section)
    pg_session.commit()
    h = _headers(client, admin)
    graded = _create_question(client, h, test.id, answer_format="numeric", accepted_answers=["12"], score=2).json()["data"]
    manual = _create_question(client, h, test.id, score=5).json()["data"]
    for qid in (graded["id"], manual["id"]):
        assert client.patch(f"/api/v1/questions/{qid}", json={"section_id": str(section.id)}, headers=h).status_code == 200
    _publish(pg_session, test)

    sh = _headers(client, student)
    attempt_id = _start(client, sh, test.id)
    _save_text(client, sh, attempt_id, graded["id"], "12")
    _save_text(client, sh, attempt_id, manual["id"], "whatever")
    assert _submit(client, sh, attempt_id)["percentage"] == 100.0

    created = client.post("/api/v1/results", json={"attempt_id": attempt_id}, headers=sh)
    assert created.status_code == 201, created.json()
    detail = client.get(f"/api/v1/results/{created.json()['data']['id']}", headers=sh).json()["data"]
    assert [s["raw_score"] for s in detail["sections"]] == [2.0]


def test_unconfigured_short_answer_behaves_exactly_as_before(client, pg_session):
    save, result = _grade_one(client, pg_session, {}, "free text")
    assert save.status_code == 200
    # Only ungraded questions -> nothing auto-scored (pre-Task-2 behavior).
    assert result["percentage"] == 0.0


def test_config_change_does_not_affect_other_tests_questions(client, pg_session):
    """Grading reads only the answered question's own row."""
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    t1, t2 = _test(pg_session), _test(pg_session)
    pg_session.commit()
    h = _headers(client, admin)
    q1 = _create_question(client, h, t1.id, answer_format="text", accepted_answers=["alpha"]).json()["data"]
    _create_question(client, h, t2.id, answer_format="text", accepted_answers=["beta"])
    _publish(pg_session, t1)
    sh = _headers(client, student)
    attempt_id = _start(client, sh, t1.id)
    _save_text(client, sh, attempt_id, q1["id"], "beta")
    assert _submit(client, sh, attempt_id)["percentage"] == 0.0
