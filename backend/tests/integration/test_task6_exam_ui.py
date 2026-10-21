"""
Task 6 — mark for review, calculator capability flag, IELTS Speaking audio
responses. Real PostgreSQL (migration 0027 applied by conftest), real HTTP
API with real logins; audio is stored in a temporary LocalDiskStorage
directory through the app's own StorageBackend dependency.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security.password_service import PasswordService
from app.main import app
from app.modules.attempts.models import Answer, TestAttempt
from app.modules.permissions.models import Permission, RolePermission
from app.modules.questions.models import Question, QuestionOption
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, Test
from app.modules.uploads.dependencies import get_storage_backend
from app.modules.uploads.models import Upload
from app.modules.uploads.storage import LocalDiskStorage
from app.modules.users.models import User, UserStatus

PASSWORD = "Integration-T3st-P@ss1"
API = "/api/v1"
WEBM = b"\x1aE\xdf\xa3" + b"\x00" * 2048  # tiny WebM-looking payload


def _user(db, role="Student") -> User:
    r = db.query(Role).filter(Role.name == role).one()
    u = User(role_id=r.id, first_name="Ui", last_name=role, email=f"ui-{role.lower().replace(' ', '-')}-{uuid.uuid4()}@example.com",
             password_hash=PasswordService().hash_password(PASSWORD), status=UserStatus.ACTIVE)
    db.add(u)
    db.flush()
    return u


def _login(client, user) -> dict:
    r = client.post(f"{API}/auth/login", json={"identifier": user.email, "password": PASSWORD})
    assert r.status_code == 200, r.json()
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.fixture
def storage(tmp_path):
    backend = LocalDiskStorage(base_dir=str(tmp_path))
    app.dependency_overrides[get_storage_backend] = lambda: backend
    try:
        yield backend
    finally:
        app.dependency_overrides.pop(get_storage_backend, None)


def _q(db, test, section=None, qtype="single_choice", module=None):
    q = Question(test_id=test.id, section_id=section.id if section else None, module_id=module.id if module else None,
                 question_text="Q", question_type=qtype, score=1)
    db.add(q)
    db.flush()
    if qtype == "single_choice":
        db.add_all([QuestionOption(question_id=q.id, option_text="right", is_correct=True),
                    QuestionOption(question_id=q.id, option_text="wrong", is_correct=False)])
        db.flush()
    db.refresh(q)
    return q


class Ctx:
    def __init__(self, client, db):
        self.client, self.db = client, db
        self.admin, self.student = _user(db, "Admin"), _user(db)
        db.commit()
        self.ah, self.sh = _login(client, self.admin), _login(client, self.student)

    def ielts(self):
        s = Subject(name=f"UI S-{uuid.uuid4()}")
        self.db.add(s)
        self.db.flush()
        test = Test(subject_id=s.id, title="IELTS UI", duration=60, question_count=0, status="published",
                    shuffle_questions=False, shuffle_answers=False, scoring_profile="ielts")
        self.db.add(test)
        self.db.flush()
        reading = ExamSection(test_id=test.id, name="Reading", order_number=0, score_component="ielts_reading")
        writing = ExamSection(test_id=test.id, name="Writing", order_number=1, score_component="ielts_writing")
        speaking = ExamSection(test_id=test.id, name="Speaking", order_number=2, score_component="ielts_speaking")
        self.db.add_all([reading, writing, speaking])
        self.db.flush()
        r1 = _q(self.db, test, reading)
        w1 = _q(self.db, test, writing, "essay")
        s1 = _q(self.db, test, speaking, "essay")
        self.db.commit()
        return test, r1, w1, s1

    def start(self, test, headers=None):
        r = self.client.post(f"{API}/attempts/start", json={"test_id": str(test.id)}, headers=headers or self.sh)
        assert r.status_code == 201, r.json()
        return r.json()["data"]["id"]

    def detail(self, attempt_id, headers=None):
        r = self.client.get(f"{API}/attempts/{attempt_id}", headers=headers or self.sh)
        assert r.status_code == 200, r.json()
        return r.json()["data"]

    def mark(self, attempt_id, q, marked, headers=None):
        return self.client.put(f"{API}/attempts/{attempt_id}/review-marks/{q.id}", json={"marked": marked}, headers=headers or self.sh)

    def upload(self, attempt_id, q, data=WEBM, mime="audio/webm;codecs=opus", headers=None):
        return self.client.post(f"{API}/attempts/{attempt_id}/questions/{q.id}/audio",
                                files={"file": ("answer.webm", data, mime)}, headers=headers or self.sh)


def _state(detail, q):
    return next(a for a in detail["answered"] if a["question_id"] == str(q.id))


def _question(detail, q):
    return next(x for x in detail["questions"] if x["id"] == str(q.id))


# --- mark for review ---------------------------------------------------------------------

def test_mark_toggle_persists_and_never_touches_answers(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, r1, w1, s1 = ctx.ielts()
    attempt_id = ctx.start(test)
    opt = next(o.id for o in r1.options if o.is_correct)
    assert client.patch(f"{API}/attempts/{attempt_id}/answer", json={"question_id": str(r1.id), "selected_option": str(opt)}, headers=ctx.sh).status_code == 200

    r = ctx.mark(attempt_id, r1, True)
    assert r.status_code == 200 and r.json()["data"]["marked"] is True
    assert ctx.mark(attempt_id, w1, True).json()["data"]["marked_question_ids"] == [str(r1.id), str(w1.id)]

    d = ctx.detail(attempt_id)
    assert set(d["marked_question_ids"]) == {str(r1.id), str(w1.id)}
    assert _state(d, r1)["is_answered"] is True and _state(d, r1)["selected_option"] == str(opt)   # answered + marked
    assert _state(d, w1)["is_answered"] is False                                                     # marked, unanswered
    assert pg_session.query(Answer).filter_by(attempt_id=uuid.UUID(attempt_id), question_id=w1.id).count() == 0

    assert ctx.mark(attempt_id, r1, False).json()["data"]["marked_question_ids"] == [str(w1.id)]
    assert ctx.mark(attempt_id, r1, False).status_code == 200            # idempotent
    d = ctx.detail(attempt_id)
    assert d["marked_question_ids"] == [str(w1.id)] and _state(d, r1)["selected_option"] == str(opt)


def test_mark_is_owner_only_and_validated(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, r1, w1, s1 = ctx.ielts()
    other = _user(pg_session)
    pg_session.commit()
    attempt_id = ctx.start(test)
    oh = _login(client, other)
    assert ctx.mark(attempt_id, r1, True, headers=oh).status_code == 404
    assert client.get(f"{API}/attempts/{attempt_id}", headers=oh).status_code == 404
    assert client.put(f"{API}/attempts/{attempt_id}/review-marks/{r1.id}", json={"marked": True}).status_code == 401
    assert client.put(f"{API}/attempts/{attempt_id}/review-marks/{uuid.uuid4()}", json={"marked": True}, headers=ctx.sh).status_code == 422
    r = client.put(f"{API}/attempts/{attempt_id}/review-marks/{r1.id}", json={"marked": True, "user_id": str(other.id)}, headers=ctx.sh)
    assert r.status_code == 422
    assert ctx.detail(attempt_id)["marked_question_ids"] == []


def test_mark_rejected_after_submit_and_after_expiry(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, r1, w1, s1 = ctx.ielts()
    test.max_attempts = 3
    pg_session.commit()
    submitted = ctx.start(test)
    assert client.post(f"{API}/attempts/{submitted}/submit", headers=ctx.sh).status_code == 200
    assert ctx.mark(submitted, r1, True).status_code == 409

    expired = ctx.start(test)
    row = pg_session.get(TestAttempt, uuid.UUID(expired))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    pg_session.commit()
    assert ctx.mark(expired, r1, True).status_code == 409


def test_mark_limited_to_current_module(client, pg_session):
    ctx = Ctx(client, pg_session)
    s = Subject(name=f"UI S-{uuid.uuid4()}")
    pg_session.add(s)
    pg_session.flush()
    test = Test(subject_id=s.id, title="Modular", duration=60, question_count=0, status="published", shuffle_questions=False, shuffle_answers=False)
    pg_session.add(test)
    pg_session.flush()
    sec = ExamSection(test_id=test.id, name="Math", order_number=0)
    pg_session.add(sec)
    pg_session.flush()
    m1, m2 = ExamModule(section_id=sec.id, name="M1", order_number=0), ExamModule(section_id=sec.id, name="M2", order_number=1)
    pg_session.add_all([m1, m2])
    pg_session.flush()
    q1, q2 = _q(pg_session, test, sec, module=m1), _q(pg_session, test, sec, module=m2)
    pg_session.commit()
    attempt_id = ctx.start(test)
    assert ctx.mark(attempt_id, q1, True).status_code == 200
    assert ctx.mark(attempt_id, q2, True).status_code == 422


# --- calculator flag ----------------------------------------------------------------------

def test_calculator_flag_follows_section_and_defaults_off(client, pg_session):
    ctx = Ctx(client, pg_session)
    s = Subject(name=f"UI S-{uuid.uuid4()}")
    pg_session.add(s)
    pg_session.flush()
    test = Test(subject_id=s.id, title="SAT UI", duration=60, question_count=0, status="published",
                shuffle_questions=False, shuffle_answers=False, scoring_profile="sat")
    pg_session.add(test)
    pg_session.flush()
    pg_session.commit()
    math = client.post(f"{API}/tests/exam-sections", json={"test_id": str(test.id), "name": "Math", "order_number": 0,
                                                           "score_component": "sat_math", "calculator_enabled": True}, headers=ctx.ah)
    assert math.status_code == 201 and math.json()["data"]["calculator_enabled"] is True
    rw = client.post(f"{API}/tests/exam-sections", json={"test_id": str(test.id), "name": "R&W", "order_number": 1,
                                                         "score_component": "sat_reading_writing"}, headers=ctx.ah)
    assert rw.json()["data"]["calculator_enabled"] is False
    qm = _q(pg_session, test, pg_session.get(ExamSection, uuid.UUID(math.json()["data"]["id"])))
    qr = _q(pg_session, test, pg_session.get(ExamSection, uuid.UUID(rw.json()["data"]["id"])))
    plain = _q(pg_session, test)
    pg_session.commit()

    d = ctx.detail(ctx.start(test))
    assert (_question(d, qm)["calculator_enabled"], _question(d, qr)["calculator_enabled"], _question(d, plain)["calculator_enabled"]) == (True, False, False)
    assert not any(q["accepts_audio"] for q in d["questions"])

    # Admin can switch it off; a null update leaves it unchanged; a teacher cannot change sections.
    sid = math.json()["data"]["id"]
    assert client.patch(f"{API}/tests/exam-sections/{sid}", json={"calculator_enabled": None}, headers=ctx.ah).json()["data"]["calculator_enabled"] is True
    assert client.patch(f"{API}/tests/exam-sections/{sid}", json={"calculator_enabled": False}, headers=ctx.ah).json()["data"]["calculator_enabled"] is False
    teacher = _user(pg_session, "Teacher")
    pg_session.commit()
    assert client.patch(f"{API}/tests/exam-sections/{sid}", json={"calculator_enabled": True}, headers=_login(client, teacher)).status_code == 403


# --- Speaking audio ---------------------------------------------------------------------------

def test_speaking_audio_upload_playback_and_rerecord(client, pg_session, storage, tmp_path):
    ctx = Ctx(client, pg_session)
    test, r1, w1, s1 = ctx.ielts()
    attempt_id = ctx.start(test)
    d = ctx.detail(attempt_id)
    assert (_question(d, s1)["accepts_audio"], _question(d, w1)["accepts_audio"], _question(d, r1)["accepts_audio"]) == (True, False, False)

    # A typed answer first (existing workflow) — audio must not erase it.
    assert client.patch(f"{API}/attempts/{attempt_id}/answer", json={"question_id": str(s1.id), "text_answer": "notes"}, headers=ctx.sh).status_code == 200
    up = ctx.upload(attempt_id, s1)
    assert up.status_code == 201, up.json()
    assert up.json()["data"] == {"question_id": str(s1.id), "mime_type": "audio/webm", "size_bytes": len(WEBM)}

    d = ctx.detail(attempt_id)
    st = _state(d, s1)
    assert (st["has_audio"], st["is_answered"], st["text_answer"]) == (True, True, "notes")
    assert "file_url" not in str(d) and "speaking-" not in str(d)

    got = client.get(f"{API}/attempts/{attempt_id}/questions/{s1.id}/audio", headers=ctx.sh)
    assert got.status_code == 200 and got.content == WEBM
    assert got.headers["content-type"].startswith("audio/webm") and "no-store" in got.headers["cache-control"]

    first = pg_session.query(Upload).filter(Upload.file_name.like(f"speaking-{s1.id}%")).one()
    first_path = first.file_url
    second = b"OggS" + b"\x01" * 1000
    assert ctx.upload(attempt_id, s1, data=second, mime="audio/ogg").status_code == 201
    assert client.get(f"{API}/attempts/{attempt_id}/questions/{s1.id}/audio", headers=ctx.sh).content == second
    pg_session.expire_all()
    assert pg_session.get(Upload, first.id).deleted_at is not None
    import os
    assert not os.path.exists(first_path)
    # Saving text afterwards keeps the audio.
    client.patch(f"{API}/attempts/{attempt_id}/answer", json={"question_id": str(s1.id), "text_answer": "edited"}, headers=ctx.sh)
    assert _state(ctx.detail(attempt_id), s1)["has_audio"] is True


@pytest.mark.parametrize("case, expected", [
    ("writing_question", 422), ("choice_question", 422), ("unknown_question", 422),
    ("bad_mime", 422), ("empty", 422), ("too_large", 413),
])
def test_speaking_audio_validation(client, pg_session, storage, case, expected):
    ctx = Ctx(client, pg_session)
    test, r1, w1, s1 = ctx.ielts()
    attempt_id = ctx.start(test)
    q, data, mime = s1, WEBM, "audio/webm"
    if case == "writing_question":
        q = w1
    elif case == "choice_question":
        q = r1
    elif case == "unknown_question":
        q = type("Q", (), {"id": uuid.uuid4()})()
    elif case == "bad_mime":
        mime = "application/x-msdownload"
    elif case == "empty":
        data = b""
    elif case == "too_large":
        data = b"\x00" * (20 * 1024 * 1024 + 1)
    r = ctx.upload(attempt_id, q, data=data, mime=mime)
    assert r.status_code == expected, r.json()
    assert pg_session.query(Answer).filter(Answer.attempt_id == uuid.UUID(attempt_id), Answer.audio_upload_id.is_not(None)).count() == 0


def test_speaking_audio_not_accepted_outside_ielts_profile(client, pg_session, storage):
    ctx = Ctx(client, pg_session)
    test, r1, w1, s1 = ctx.ielts()
    test.scoring_profile = None
    pg_session.commit()
    attempt_id = ctx.start(test)
    assert _question(ctx.detail(attempt_id), s1)["accepts_audio"] is False
    assert ctx.upload(attempt_id, s1).status_code == 422


def test_speaking_audio_owner_only_and_active_only(client, pg_session, storage):
    ctx = Ctx(client, pg_session)
    test, r1, w1, s1 = ctx.ielts()
    other = _user(pg_session)
    pg_session.commit()
    attempt_id = ctx.start(test)
    assert ctx.upload(attempt_id, s1).status_code == 201
    oh = _login(client, other)
    assert ctx.upload(attempt_id, s1, headers=oh).status_code == 404
    assert client.get(f"{API}/attempts/{attempt_id}/questions/{s1.id}/audio", headers=oh).status_code == 404
    assert client.get(f"{API}/attempts/{attempt_id}/questions/{s1.id}/audio").status_code == 401
    assert client.get(f"{API}/attempts/{attempt_id}/questions/{w1.id}/audio", headers=ctx.sh).status_code == 404  # nothing recorded
    assert client.post(f"{API}/attempts/{attempt_id}/submit", headers=ctx.sh).status_code == 200
    assert ctx.upload(attempt_id, s1).status_code == 409
    # The owner can still replay their own recording after submitting.
    assert client.get(f"{API}/attempts/{attempt_id}/questions/{s1.id}/audio", headers=ctx.sh).status_code == 200


def test_graders_access_audio_with_permission_only(client, pg_session, storage):
    ctx = Ctx(client, pg_session)
    test, r1, w1, s1 = ctx.ielts()
    attempt_id = ctx.start(test)
    assert ctx.upload(attempt_id, s1).status_code == 201
    url = f"{API}/grading/submissions/{attempt_id}/{s1.id}"
    # Not gradable while the attempt is still in progress.
    assert client.get(f"{url}/audio", headers=ctx.ah).status_code == 404
    assert client.post(f"{API}/attempts/{attempt_id}/submit", headers=ctx.sh).status_code == 200

    assert client.get(url, headers=ctx.ah).json()["data"]["has_audio"] is True
    got = client.get(f"{url}/audio", headers=ctx.ah)
    assert got.status_code == 200 and got.content == WEBM
    assert client.get(f"{API}/grading/submissions/{attempt_id}/{w1.id}/audio", headers=ctx.ah).status_code == 404

    teacher = _user(pg_session, "Teacher")
    pg_session.commit()
    th = _login(client, teacher)
    for h in (th, ctx.sh):
        assert client.get(f"{url}/audio", headers=h).status_code == 403
    role = pg_session.query(Role).filter(Role.name == "Teacher").one()
    perm = pg_session.query(Permission).filter(Permission.code == "GRADE_SUBMISSIONS").one()
    pg_session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    pg_session.commit()
    assert client.get(f"{url}/audio", headers=th).status_code == 200


def test_task5_grading_still_works_for_speaking_with_audio(client, pg_session, storage):
    ctx = Ctx(client, pg_session)
    rubric = client.post(f"{API}/grading/rubrics", json={"score_component": "ielts_speaking", "name": "Speaking",
                                                         "criteria": [{"key": "fluency", "label": "Fluency", "min": 0, "max": 9, "step": 1}],
                                                         "rounding": "half_up", "is_validated": False}, headers=ctx.ah)
    assert rubric.status_code == 201
    test, r1, w1, s1 = ctx.ielts()
    attempt_id = ctx.start(test)
    assert ctx.upload(attempt_id, s1).status_code == 201
    assert client.post(f"{API}/attempts/{attempt_id}/submit", headers=ctx.sh).status_code == 200
    url = f"{API}/grading/submissions/{attempt_id}/{s1.id}"
    assert client.put(f"{url}/draft", json={"criterion_scores": {"fluency": 7}}, headers=ctx.ah).status_code == 200
    final = client.post(f"{url}/finalize", headers=ctx.ah)
    assert final.status_code == 200 and final.json()["data"]["reported_score"] == 7.0
