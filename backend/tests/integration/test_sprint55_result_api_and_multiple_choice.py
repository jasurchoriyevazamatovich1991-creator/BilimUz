"""
Sprint 55 — ResultSection API Exposure + Multiple-Choice Answer Router
Fix, integration tests against real PostgreSQL (Sprint 40's
infrastructure — pg_session, TEST_DATABASE_URL). Real HTTP requests
through TestClient with real JWT tokens, matching the established
pattern from tests/integration/test_question_group_api.py.

Scope B (multiple_choice router bug): PATCH /attempts/{id}/answer never
forwarded SaveAnswerRequest.selected_options to AttemptService.save_answer()
— every real HTTP multiple_choice answer was silently scored as
unanswered. Fixed in app/modules/attempts/router.py.

Scope A (ResultSection API exposure): GET /results/{id} now returns a
"sections" list built from Sprint 54's ResultSection rows.
"""
import uuid

from fastapi.testclient import TestClient

from app.core.security.dependencies import get_jwt_service
from app.main import app
from app.modules.attempts.models import Answer
from app.modules.questions.models import Question, QuestionOption
from app.modules.results.models import Result, ResultSection
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamSection, Test, TestStatus
from app.modules.users.models import User, UserStatus


# --- Shared helpers ---------------------------------------------------------

def _make_user(pg_session, role_name="Student") -> User:
    role = pg_session.query(Role).filter(Role.name == role_name).one()
    user = User(role_id=role.id, first_name="S55", last_name=role_name, email=f"s55-{role_name}-{uuid.uuid4()}@example.com", password_hash="x", status=UserStatus.ACTIVE)
    pg_session.add(user)
    pg_session.flush()
    return user


def _auth(user: User) -> dict:
    token = get_jwt_service().create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _make_test(pg_session, max_attempts=None) -> Test:
    subject = Subject(name=f"S55 Subject {uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(
        subject_id=subject.id, title="Sprint 55 Test", duration=60,
        question_count=0, status=TestStatus.PUBLISHED,
        shuffle_questions=False, shuffle_answers=False, max_attempts=max_attempts,
    )
    pg_session.add(test)
    pg_session.flush()
    return test


def _add_section_with_questions(pg_session, test: Test, order_number: int, count: int) -> ExamSection:
    section = ExamSection(test_id=test.id, name=f"Section-{order_number}", order_number=order_number)
    pg_session.add(section)
    pg_session.flush()
    for i in range(count):
        q = Question(test_id=test.id, question_text=f"Sec{order_number} Q{i}", question_type="single_choice", score=1, section_id=section.id)
        pg_session.add(q)
        pg_session.flush()
        pg_session.add_all([
            QuestionOption(question_id=q.id, option_text="Correct", is_correct=True),
            QuestionOption(question_id=q.id, option_text="Wrong", is_correct=False),
        ])
        pg_session.flush()
    return section


def _add_plain_single_choice_questions(pg_session, test: Test, count: int) -> None:
    for i in range(count):
        q = Question(test_id=test.id, question_text=f"Plain Q{i}", question_type="single_choice", score=1)
        pg_session.add(q)
        pg_session.flush()
        pg_session.add_all([
            QuestionOption(question_id=q.id, option_text="Correct", is_correct=True),
            QuestionOption(question_id=q.id, option_text="Wrong", is_correct=False),
        ])
        pg_session.flush()


def _add_multiple_choice_question(pg_session, test: Test) -> Question:
    """A multiple_choice question with TWO correct options and one
    wrong one — score=2 (one point per correct option would be a
    stretch of the existing scoring model; instead this question is
    worth 2 points total, all-or-nothing per PercentageScoringStrategy's
    existing multiple_choice semantics: correct iff the selected set is
    EXACTLY the correct set)."""
    q = Question(test_id=test.id, question_text="Pick both correct answers", question_type="multiple_choice", score=2)
    pg_session.add(q)
    pg_session.flush()
    correct_1 = QuestionOption(question_id=q.id, option_text="Correct 1", is_correct=True)
    correct_2 = QuestionOption(question_id=q.id, option_text="Correct 2", is_correct=True)
    wrong = QuestionOption(question_id=q.id, option_text="Wrong", is_correct=False)
    pg_session.add_all([correct_1, correct_2, wrong])
    pg_session.flush()
    return q


def _start_attempt(client, test: Test, auth: dict) -> dict:
    r = client.post("/api/v1/attempts/start", json={"test_id": str(test.id)}, headers=auth)
    assert r.status_code == 201, r.text
    attempt = r.json()["data"]
    # AttemptOut (the /start response) deliberately excludes
    # question_order — fetch the real, persisted question order via
    # GET /attempts/{id} (AttemptDetailOut.questions), the same way an
    # actual client would.
    detail = client.get(f"/api/v1/attempts/{attempt['id']}", headers=auth)
    assert detail.status_code == 200, detail.text
    attempt["question_order"] = [q["id"] for q in detail.json()["data"]["questions"]]
    return attempt


def _answer_all_correct(client, attempt_id: str, question_ids: list, auth: dict, pg_session) -> None:
    for qid in question_ids:
        correct = pg_session.query(QuestionOption).filter(QuestionOption.question_id == uuid.UUID(str(qid)), QuestionOption.is_correct.is_(True)).first()
        r = client.patch(f"/api/v1/attempts/{attempt_id}/answer", json={"question_id": str(qid), "selected_option": str(correct.id)}, headers=auth)
        assert r.status_code == 200, r.text


def _submit(client, attempt_id: str, auth: dict) -> dict:
    r = client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _create_result(client, attempt_id: str, auth: dict) -> dict:
    r = client.post("/api/v1/results", json={"attempt_id": attempt_id}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _get_result(client, result_id: str, auth: dict):
    return client.get(f"/api/v1/results/{result_id}", headers=auth)


# =============================================================================
# SCOPE B — multiple_choice router regression
# =============================================================================

def test_multiple_choice_answer_persists_and_scores_correctly_through_real_router(client, pg_session):
    """This is the router-level regression test the bug required: it
    goes through the ACTUAL HTTP router (PATCH /attempts/{id}/answer),
    not AttemptService directly — the pre-fix code silently dropped
    selected_options here and would have scored this attempt 0/2
    instead of 2/2."""
    student = _make_user(pg_session, "Student")
    auth = _auth(student)
    test = _make_test(pg_session)
    question = _add_multiple_choice_question(pg_session, test)
    pg_session.commit()

    attempt = _start_attempt(client, test, auth)
    correct_ids = [str(o.id) for o in pg_session.query(QuestionOption).filter(QuestionOption.question_id == question.id, QuestionOption.is_correct.is_(True)).all()]
    assert len(correct_ids) == 2

    r = client.patch(
        f"/api/v1/attempts/{attempt['id']}/answer",
        json={"question_id": str(question.id), "selected_options": correct_ids},
        headers=auth,
    )
    assert r.status_code == 200, r.text

    # 1. Verify the Answer persisted with the expected selected_options.
    saved = pg_session.query(Answer).filter(Answer.attempt_id == attempt["id"], Answer.question_id == question.id).one()
    assert saved.selected_option is None
    assert sorted(str(x) for x in saved.selected_options) == sorted(correct_ids)

    # 2. Verify is_correct is calculated correctly.
    assert saved.is_correct is True

    # 3. Verify final scoring uses that answer correctly.
    submit_result = _submit(client, attempt["id"], auth)
    assert submit_result["score"] == 2.0
    assert submit_result["percentage"] == 100.0


def test_multiple_choice_wrong_selection_scores_zero_through_real_router(client, pg_session):
    """Complementary case: selecting only one of the two correct
    options (an incomplete/wrong set) must score as incorrect — proves
    the router fix passes through the REAL selection, not just "any
    selection is truthy"."""
    student = _make_user(pg_session, "Student")
    auth = _auth(student)
    test = _make_test(pg_session)
    question = _add_multiple_choice_question(pg_session, test)
    pg_session.commit()

    attempt = _start_attempt(client, test, auth)
    one_correct = pg_session.query(QuestionOption).filter(QuestionOption.question_id == question.id, QuestionOption.is_correct.is_(True)).first()

    r = client.patch(
        f"/api/v1/attempts/{attempt['id']}/answer",
        json={"question_id": str(question.id), "selected_options": [str(one_correct.id)]},
        headers=auth,
    )
    assert r.status_code == 200, r.text

    saved = pg_session.query(Answer).filter(Answer.attempt_id == attempt["id"], Answer.question_id == question.id).one()
    assert saved.is_correct is False

    submit_result = _submit(client, attempt["id"], auth)
    assert submit_result["score"] == 0.0
    assert submit_result["percentage"] == 0.0


# =============================================================================
# SCOPE A — ResultSection API exposure
# =============================================================================

def test_modular_result_api_returns_both_sections_with_matching_scores(client, pg_session):
    student = _make_user(pg_session, "Student")
    auth = _auth(student)
    test = _make_test(pg_session)
    section_a = _add_section_with_questions(pg_session, test, order_number=0, count=2)
    section_b = _add_section_with_questions(pg_session, test, order_number=1, count=2)
    pg_session.commit()

    attempt = _start_attempt(client, test, auth)
    _answer_all_correct(client, attempt["id"], attempt["question_order"], auth, pg_session)
    _submit(client, attempt["id"], auth)
    result = _create_result(client, attempt["id"], auth)

    r = _get_result(client, result["id"], auth)
    assert r.status_code == 200, r.text
    body = r.json()["data"]

    assert "sections" in body
    assert len(body["sections"]) == 2
    section_ids_in_response = {s["section_id"] for s in body["sections"]}
    assert section_ids_in_response == {str(section_a.id), str(section_b.id)}

    db_sections = {str(rs.section_id): rs for rs in pg_session.query(ResultSection).filter(ResultSection.result_id == uuid.UUID(result["id"])).all()}
    for s in body["sections"]:
        db_row = db_sections[s["section_id"]]
        assert s["id"] == str(db_row.id)
        assert float(s["raw_score"]) == float(db_row.raw_score)
        assert s["scaled_score"] is None

    # Deterministic ordering by ExamSection.order_number.
    assert body["sections"][0]["section_id"] == str(section_a.id)
    assert body["sections"][1]["section_id"] == str(section_b.id)


def test_non_modular_result_api_returns_empty_sections_list(client, pg_session):
    student = _make_user(pg_session, "Student")
    auth = _auth(student)
    test = _make_test(pg_session)
    _add_plain_single_choice_questions(pg_session, test, count=2)
    pg_session.commit()

    attempt = _start_attempt(client, test, auth)
    _answer_all_correct(client, attempt["id"], attempt["question_order"], auth, pg_session)
    _submit(client, attempt["id"], auth)
    result = _create_result(client, attempt["id"], auth)

    r = _get_result(client, result["id"], auth)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["sections"] == []
    # Backward compatibility — existing fields still present, unchanged shape.
    assert body["score"] == 2.0
    assert body["percentage"] == 100.0


def test_non_owner_cannot_read_result_or_its_sections(client, pg_session):
    owner = _make_user(pg_session, "Student")
    intruder = _make_user(pg_session, "Student")
    owner_auth, intruder_auth = _auth(owner), _auth(intruder)
    test = _make_test(pg_session)
    _add_section_with_questions(pg_session, test, order_number=0, count=1)
    pg_session.commit()

    attempt = _start_attempt(client, test, owner_auth)
    _answer_all_correct(client, attempt["id"], attempt["question_order"], owner_auth, pg_session)
    _submit(client, attempt["id"], owner_auth)
    result = _create_result(client, attempt["id"], owner_auth)

    r = _get_result(client, result["id"], intruder_auth)
    assert r.status_code == 404, r.text
    assert "sections" not in r.text or r.json().get("data") is None


def test_result_sections_never_leak_across_results(client, pg_session):
    """Section isolation: two different students' modular results for
    the SAME test must never mix ResultSection rows."""
    student_a = _make_user(pg_session, "Student")
    student_b = _make_user(pg_session, "Student")
    auth_a, auth_b = _auth(student_a), _auth(student_b)
    test = _make_test(pg_session)
    _add_section_with_questions(pg_session, test, order_number=0, count=1)
    pg_session.commit()

    attempt_a = _start_attempt(client, test, auth_a)
    _answer_all_correct(client, attempt_a["id"], attempt_a["question_order"], auth_a, pg_session)
    _submit(client, attempt_a["id"], auth_a)
    result_a = _create_result(client, attempt_a["id"], auth_a)

    attempt_b = _start_attempt(client, test, auth_b)
    _answer_all_correct(client, attempt_b["id"], attempt_b["question_order"], auth_b, pg_session)
    _submit(client, attempt_b["id"], auth_b)
    result_b = _create_result(client, attempt_b["id"], auth_b)

    body_a = _get_result(client, result_a["id"], auth_a).json()["data"]
    body_b = _get_result(client, result_b["id"], auth_b).json()["data"]

    assert len(body_a["sections"]) == 1
    assert len(body_b["sections"]) == 1
    assert body_a["sections"][0]["id"] != body_b["sections"][0]["id"]


def test_scaled_score_remains_null_in_api_response(client, pg_session):
    student = _make_user(pg_session, "Student")
    auth = _auth(student)
    test = _make_test(pg_session)
    _add_section_with_questions(pg_session, test, order_number=0, count=1)
    pg_session.commit()

    attempt = _start_attempt(client, test, auth)
    _answer_all_correct(client, attempt["id"], attempt["question_order"], auth, pg_session)
    _submit(client, attempt["id"], auth)
    result = _create_result(client, attempt["id"], auth)

    body = _get_result(client, result["id"], auth).json()["data"]
    assert all(s["scaled_score"] is None for s in body["sections"])


def test_existing_results_history_and_result_out_contract_unchanged(client, pg_session):
    """Backward compatibility: GET /results/me (list view, ResultOut)
    is untouched by this sprint — no 'sections' field, no shape change."""
    student = _make_user(pg_session, "Student")
    auth = _auth(student)
    test = _make_test(pg_session)
    _add_section_with_questions(pg_session, test, order_number=0, count=1)
    pg_session.commit()

    attempt = _start_attempt(client, test, auth)
    _answer_all_correct(client, attempt["id"], attempt["question_order"], auth, pg_session)
    _submit(client, attempt["id"], auth)
    _create_result(client, attempt["id"], auth)

    r = client.get("/api/v1/results/me", headers=auth)
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 1
    assert "sections" not in items[0]
    assert set(items[0].keys()) == {"id", "attempt_id", "user_id", "test_id", "score", "percentage", "is_passed", "status", "created_at"}
