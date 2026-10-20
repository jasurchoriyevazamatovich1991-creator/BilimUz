"""
Task 3 — media attached to a QuestionGroup (IELTS Listening section audio),
against real PostgreSQL (migration 0024 applied by conftest).

Covers the admin API (attach/list/remove, roles, validation, duplicates),
the DB constraints, student delivery (descriptors only, no URL), the
group-media view-url authorization rules, and regression of Task 1
question-level media.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security.password_service import PasswordService
from app.main import app
from app.modules.attempts.exceptions import (
    AttemptMediaNotFoundException,
    AttemptMediaUnavailableException,
    AttemptNotActiveException,
    AttemptNotFoundException,
)
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.questions.models import Question, QuestionMedia, QuestionOption
from app.modules.questions.repository import MediaRepository, OptionRepository, QuestionRepository
from app.modules.roles.models import Role
from app.modules.subjects.models import Subject
from app.modules.tests.models import ExamModule, ExamSection, QuestionGroup, QuestionGroupMedia, Test
from app.modules.tests.repository import (
    ExamModuleRepository,
    ExamSectionRepository,
    QuestionGroupMediaRepository,
    QuestionGroupRepository,
    TestRepository,
)
from app.modules.uploads.dependencies import get_storage_backend
from app.modules.uploads.models import Upload
from app.modules.uploads.repository import UploadRepository
from app.modules.uploads.storage import StorageBackend
from app.modules.users.models import User, UserStatus

PASSWORD = "Integration-T3st-P@ss1"


class FakeSigningStorage(StorageBackend):
    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def save(self, filename, stream):  # pragma: no cover
        raise NotImplementedError

    def delete(self, file_url):  # pragma: no cover
        raise NotImplementedError

    def read(self, file_url):  # pragma: no cover
        raise NotImplementedError

    def create_presigned_download(self, object_key: str, expires_in: int) -> str:
        self.calls.append((object_key, expires_in))
        return f"https://signed.example.test/{object_key}?expires={expires_in}"


# --- helpers ----------------------------------------------------------------------

def _user(pg_session, role_name="Student") -> User:
    role = pg_session.query(Role).filter(Role.name == role_name).one()
    u = User(role_id=role.id, first_name="Group", last_name=role_name,
             email=f"gm-{role_name.lower().replace(' ', '-')}-{uuid.uuid4()}@example.com",
             password_hash=PasswordService().hash_password(PASSWORD), status=UserStatus.ACTIVE)
    pg_session.add(u)
    pg_session.flush()
    return u


def _headers(client, user) -> dict:
    r = client.post("/api/v1/auth/login", json={"identifier": user.email, "password": PASSWORD})
    assert r.status_code == 200, r.json()
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _test(pg_session) -> Test:
    s = Subject(name=f"GM S-{uuid.uuid4()}")
    pg_session.add(s)
    pg_session.flush()
    t = Test(subject_id=s.id, title="Listening", duration=60, question_count=0, status="published",
             shuffle_questions=False, shuffle_answers=False)
    pg_session.add(t)
    pg_session.flush()
    return t


def _group(pg_session, test_id, module_id=None, order=0, stimulus=None) -> QuestionGroup:
    g = QuestionGroup(test_id=test_id, module_id=module_id, title=f"Section {order + 1}", stimulus_text=stimulus, order_number=order)
    pg_session.add(g)
    pg_session.flush()
    return g


def _question(pg_session, test_id, group_id=None, module_id=None, text="Q") -> Question:
    q = Question(test_id=test_id, question_text=text, question_type="single_choice", score=1, group_id=group_id, module_id=module_id)
    pg_session.add(q)
    pg_session.flush()
    pg_session.add_all([QuestionOption(question_id=q.id, option_text="A", is_correct=True),
                        QuestionOption(question_id=q.id, option_text="B", is_correct=False)])
    pg_session.flush()
    return q


def _upload(pg_session, owner, file_type="audio", status="ready") -> Upload:
    u = Upload(user_id=owner.id, file_name=f"part1.{'mp3' if file_type == 'audio' else 'png'}",
               file_url=f"private/{file_type}/{uuid.uuid4()}", file_type=file_type, size_bytes=2048, status=status)
    pg_session.add(u)
    pg_session.flush()
    return u


def _group_media(pg_session, group, upload, created_at=None) -> QuestionGroupMedia:
    m = QuestionGroupMedia(group_id=group.id, upload_id=upload.id, media_type=upload.file_type)
    if created_at is not None:
        m.created_at = created_at
    pg_session.add(m)
    pg_session.flush()
    return m


def _service(pg_session, storage=None) -> AttemptService:
    return AttemptService(
        AttemptRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
        QuestionRepository(pg_session), OptionRepository(pg_session),
        ModuleExecutionService(
            ExamModuleRepository(pg_session), AttemptModuleProgressRepository(pg_session),
            QuestionRepository(pg_session), AnswerRepository(pg_session), AttemptRepository(pg_session),
        ),
        ExamModuleRepository(pg_session), ExamSectionRepository(pg_session), QuestionGroupRepository(pg_session),
        None, MediaRepository(pg_session), UploadRepository(pg_session), storage or FakeSigningStorage(),
        QuestionGroupMediaRepository(pg_session),
    )


def _start(pg_session, service, test, student):
    a = service.start_attempt(test.id, student.id)
    pg_session.commit()
    return a


@pytest.fixture
def signing_storage():
    storage = FakeSigningStorage()
    app.dependency_overrides[get_storage_backend] = lambda: storage
    try:
        yield storage
    finally:
        app.dependency_overrides.pop(get_storage_backend, None)


# --- admin API ------------------------------------------------------------------------

def test_admin_attaches_lists_and_removes_group_audio(client, pg_session):
    admin = _user(pg_session, "Admin")
    test = _test(pg_session)
    group = _group(pg_session, test.id)
    audio = _upload(pg_session, admin)
    pg_session.commit()
    h = _headers(client, admin)

    added = client.post(f"/api/v1/tests/question-groups/{group.id}/media", json={"upload_id": str(audio.id)}, headers=h)
    assert added.status_code == 201, added.json()
    media = added.json()["data"]
    assert (media["group_id"], media["upload_id"], media["media_type"]) == (str(group.id), str(audio.id), "audio")
    assert "file_url" not in media

    listed = client.get(f"/api/v1/tests/question-groups/{group.id}", headers=h).json()["data"]
    assert [m["id"] for m in listed["media"]] == [media["id"]]
    all_groups = client.get("/api/v1/tests/question-groups", params={"test_id": str(test.id)}, headers=h).json()["data"]
    assert all_groups[0]["media"][0]["media_type"] == "audio"

    removed = client.delete(f"/api/v1/tests/question-groups/{group.id}/media/{media['id']}", headers=h)
    assert removed.status_code == 204
    assert client.get(f"/api/v1/tests/question-groups/{group.id}", headers=h).json()["data"]["media"] == []
    # Removing the attachment leaves the Upload itself untouched.
    pg_session.expire_all()
    assert pg_session.get(Upload, audio.id).deleted_at is None
    # And the same upload can be attached again after removal.
    again = client.post(f"/api/v1/tests/question-groups/{group.id}/media", json={"upload_id": str(audio.id)}, headers=h)
    assert again.status_code == 201


def test_media_type_comes_from_upload_not_client(client, pg_session):
    admin = _user(pg_session, "Admin")
    test = _test(pg_session)
    group = _group(pg_session, test.id)
    image = _upload(pg_session, admin, file_type="image")
    pg_session.commit()
    r = client.post(f"/api/v1/tests/question-groups/{group.id}/media",
                    json={"upload_id": str(image.id), "media_type": "audio"}, headers=_headers(client, admin))
    assert r.status_code == 201, r.json()
    assert r.json()["data"]["media_type"] == "image"


@pytest.mark.parametrize("case, expected", [
    ("video", 422), ("document", 422), ("pending", 409), ("missing_upload", 404),
    ("missing_group", 404), ("deleted_group", 404), ("duplicate", 409),
])
def test_attach_validation(client, pg_session, case, expected):
    admin = _user(pg_session, "Admin")
    test = _test(pg_session)
    group = _group(pg_session, test.id)
    upload_type = case if case in ("video", "document") else "audio"
    upload = _upload(pg_session, admin, file_type=upload_type, status="pending" if case == "pending" else "ready")
    group_id = group.id
    upload_id = upload.id
    if case == "missing_upload":
        upload_id = uuid.uuid4()
    if case == "missing_group":
        group_id = uuid.uuid4()
    if case == "deleted_group":
        group.deleted_at = datetime.now(timezone.utc)
    if case == "duplicate":
        _group_media(pg_session, group, upload)
    pg_session.commit()

    r = client.post(f"/api/v1/tests/question-groups/{group_id}/media", json={"upload_id": str(upload_id)}, headers=_headers(client, admin))
    assert r.status_code == expected, r.json()
    assert r.json()["success"] is False


def test_remove_media_of_another_group_is_404(client, pg_session):
    admin = _user(pg_session, "Admin")
    test = _test(pg_session)
    g1, g2 = _group(pg_session, test.id, order=0), _group(pg_session, test.id, order=1)
    m = _group_media(pg_session, g1, _upload(pg_session, admin))
    pg_session.commit()
    r = client.delete(f"/api/v1/tests/question-groups/{g2.id}/media/{m.id}", headers=_headers(client, admin))
    assert r.status_code == 404


@pytest.mark.parametrize("role", ["Student", "Teacher", "Moderator"])
def test_non_admin_roles_cannot_manage_group_media(client, pg_session, role):
    admin, actor = _user(pg_session, "Admin"), _user(pg_session, role)
    test = _test(pg_session)
    group = _group(pg_session, test.id)
    upload = _upload(pg_session, admin)
    m = _group_media(pg_session, group, upload)
    pg_session.commit()
    h = _headers(client, actor)
    assert client.post(f"/api/v1/tests/question-groups/{group.id}/media", json={"upload_id": str(upload.id)}, headers=h).status_code == 403
    assert client.delete(f"/api/v1/tests/question-groups/{group.id}/media/{m.id}", headers=h).status_code == 403
    assert client.get(f"/api/v1/tests/question-groups/{group.id}", headers=h).status_code == 403


def test_unauthenticated_requests_are_401(client, pg_session):
    gid, mid = uuid.uuid4(), uuid.uuid4()
    assert client.post(f"/api/v1/tests/question-groups/{gid}/media", json={"upload_id": str(uuid.uuid4())}).status_code == 401
    assert client.get(f"/api/v1/attempts/{uuid.uuid4()}/group-media/{mid}/view-url").status_code == 401


def test_db_rejects_unsupported_type_and_active_duplicates(pg_session):
    admin = _user(pg_session, "Admin")
    test = _test(pg_session)
    group = _group(pg_session, test.id)
    upload = _upload(pg_session, admin)
    pg_session.commit()

    pg_session.add(QuestionGroupMedia(group_id=group.id, upload_id=upload.id, media_type="video"))
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()

    first = QuestionGroupMedia(group_id=group.id, upload_id=upload.id, media_type="audio")
    pg_session.add(first)
    pg_session.flush()
    pg_session.add(QuestionGroupMedia(group_id=group.id, upload_id=upload.id, media_type="audio"))
    with pytest.raises(IntegrityError):
        pg_session.flush()
    pg_session.rollback()


def test_db_allows_reattach_after_soft_delete(pg_session):
    admin = _user(pg_session, "Admin")
    test = _test(pg_session)
    group = _group(pg_session, test.id)
    upload = _upload(pg_session, admin)
    old = _group_media(pg_session, group, upload)
    old.deleted_at = datetime.now(timezone.utc)
    pg_session.flush()
    _group_media(pg_session, group, upload)  # no IntegrityError


# --- student delivery -------------------------------------------------------------------

def test_grouped_questions_carry_group_audio_descriptors_without_urls(pg_session):
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    group = _group(pg_session, test.id, stimulus=None)
    base = datetime.now(timezone.utc)
    audio = _upload(pg_session, admin)
    image = _upload(pg_session, admin, file_type="image")
    m_audio = _group_media(pg_session, group, audio, created_at=base)
    m_image = _group_media(pg_session, group, image, created_at=base + timedelta(seconds=1))
    _question(pg_session, test.id, group_id=group.id, text="Q1")
    _question(pg_session, test.id, group_id=group.id, text="Q2")
    _question(pg_session, test.id, text="Ungrouped")
    pg_session.commit()
    service = _service(pg_session)
    attempt = _start(pg_session, service, test, student)

    detail = service.get_attempt_detail(attempt.id, student.id)
    q1, q2, plain = detail.questions
    expected = [{"id": m_audio.id, "media_type": "audio"}, {"id": m_image.id, "media_type": "image"}]
    assert [m.model_dump() for m in q1.group_media] == expected
    assert [m.model_dump() for m in q2.group_media] == expected
    assert plain.group_media == []
    assert audio.file_url not in str(detail.model_dump())
    # Question-level media list is unaffected.
    assert q1.media == []


def test_deleted_group_media_and_deleted_group_are_not_delivered(pg_session):
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    g_live, g_deleted = _group(pg_session, test.id, order=0), _group(pg_session, test.id, order=1)
    removed = _group_media(pg_session, g_live, _upload(pg_session, admin))
    removed.deleted_at = datetime.now(timezone.utc)
    hidden = _group_media(pg_session, g_deleted, _upload(pg_session, admin))
    g_deleted.deleted_at = datetime.now(timezone.utc)
    _question(pg_session, test.id, group_id=g_live.id)
    _question(pg_session, test.id, group_id=g_deleted.id)
    pg_session.commit()
    service = _service(pg_session)
    attempt = _start(pg_session, service, test, student)

    detail = service.get_attempt_detail(attempt.id, student.id)
    assert all(q.group_media == [] for q in detail.questions)
    for m in (removed, hidden):
        with pytest.raises(AttemptMediaNotFoundException):
            service.get_group_media_view_url(attempt.id, m.id, student.id)


def test_view_url_for_delivered_group_audio(pg_session):
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    group = _group(pg_session, test.id)
    audio = _upload(pg_session, admin)
    m = _group_media(pg_session, group, audio)
    _question(pg_session, test.id, group_id=group.id)
    pg_session.commit()
    storage = FakeSigningStorage()
    service = _service(pg_session, storage)
    attempt = _start(pg_session, service, test, student)

    out = service.get_group_media_view_url(attempt.id, m.id, student.id)
    assert out.media_type == "audio" and out.view_url.startswith("https://signed.example.test/")
    assert storage.calls == [(audio.file_url, 300)]


def test_view_url_denied_for_other_student_other_test_and_unknown_id(pg_session):
    admin, owner, intruder = _user(pg_session, "Admin"), _user(pg_session), _user(pg_session)
    test, other_test = _test(pg_session), _test(pg_session)
    group = _group(pg_session, test.id)
    m = _group_media(pg_session, group, _upload(pg_session, admin))
    _question(pg_session, test.id, group_id=group.id)
    other_group = _group(pg_session, other_test.id)
    foreign = _group_media(pg_session, other_group, _upload(pg_session, admin))
    _question(pg_session, other_test.id, group_id=other_group.id)
    pg_session.commit()
    service = _service(pg_session)
    attempt = _start(pg_session, service, test, owner)

    with pytest.raises(AttemptNotFoundException):
        service.get_group_media_view_url(attempt.id, m.id, intruder.id)
    with pytest.raises(AttemptMediaNotFoundException):
        service.get_group_media_view_url(attempt.id, foreign.id, owner.id)
    with pytest.raises(AttemptMediaNotFoundException):
        service.get_group_media_view_url(attempt.id, uuid.uuid4(), owner.id)


def test_question_media_id_is_not_accepted_as_group_media_and_vice_versa(pg_session):
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    group = _group(pg_session, test.id)
    gm = _group_media(pg_session, group, _upload(pg_session, admin))
    q = _question(pg_session, test.id, group_id=group.id)
    qm = QuestionMedia(question_id=q.id, media_type="image", file_url="https://cdn.example.test/x.png")
    pg_session.add(qm)
    pg_session.commit()
    service = _service(pg_session)
    attempt = _start(pg_session, service, test, student)

    with pytest.raises(AttemptMediaNotFoundException):
        service.get_group_media_view_url(attempt.id, qm.id, student.id)
    with pytest.raises(AttemptMediaNotFoundException):
        service.get_media_view_url(attempt.id, gm.id, student.id)


def test_group_of_not_yet_routed_module_is_hidden(pg_session):
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    section = ExamSection(test_id=test.id, name="Listening", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    m1 = ExamModule(section_id=section.id, name="Part 1", order_number=0)
    m2 = ExamModule(section_id=section.id, name="Part 2", order_number=1)
    pg_session.add_all([m1, m2])
    pg_session.flush()
    g1 = _group(pg_session, test.id, module_id=m1.id, order=0)
    g2 = _group(pg_session, test.id, module_id=m2.id, order=1)
    current = _group_media(pg_session, g1, _upload(pg_session, admin))
    future = _group_media(pg_session, g2, _upload(pg_session, admin))
    _question(pg_session, test.id, group_id=g1.id, module_id=m1.id)
    _question(pg_session, test.id, group_id=g2.id, module_id=m2.id)
    pg_session.commit()
    service = _service(pg_session)
    attempt = _start(pg_session, service, test, student)

    delivered = {m.id for q in service.get_attempt_detail(attempt.id, student.id).questions for m in q.group_media}
    assert delivered == {current.id}
    assert service.get_group_media_view_url(attempt.id, current.id, student.id).view_url
    with pytest.raises(AttemptMediaNotFoundException):
        service.get_group_media_view_url(attempt.id, future.id, student.id)


def test_finished_attempt_cannot_fetch_group_audio(pg_session):
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    group = _group(pg_session, test.id)
    m = _group_media(pg_session, group, _upload(pg_session, admin))
    _question(pg_session, test.id, group_id=group.id)
    pg_session.commit()
    service = _service(pg_session)
    attempt = _start(pg_session, service, test, student)
    service.submit_attempt(attempt.id, student.id)
    pg_session.commit()

    with pytest.raises(AttemptNotActiveException):
        service.get_group_media_view_url(attempt.id, m.id, student.id)


def test_deleted_or_unfinalized_upload(pg_session):
    admin, student = _user(pg_session, "Admin"), _user(pg_session)
    test = _test(pg_session)
    group = _group(pg_session, test.id)
    gone_upload = _upload(pg_session, admin)
    gone = _group_media(pg_session, group, gone_upload)
    gone_upload.deleted_at = datetime.now(timezone.utc)
    failed = _group_media(pg_session, group, _upload(pg_session, admin, status="failed"))
    _question(pg_session, test.id, group_id=group.id)
    pg_session.commit()
    service = _service(pg_session)
    attempt = _start(pg_session, service, test, student)

    with pytest.raises(AttemptMediaNotFoundException):
        service.get_group_media_view_url(attempt.id, gone.id, student.id)
    with pytest.raises(AttemptMediaUnavailableException):
        service.get_group_media_view_url(attempt.id, failed.id, student.id)


# --- real HTTP, end to end ---------------------------------------------------------------

def test_http_end_to_end_group_audio_and_task1_question_media_regression(client, pg_session, signing_storage):
    admin, student, other = _user(pg_session, "Admin"), _user(pg_session), _user(pg_session)
    test = _test(pg_session)
    group = _group(pg_session, test.id, stimulus="Listen to the conversation.")
    q = _question(pg_session, test.id, group_id=group.id)
    q_image = _upload(pg_session, admin, file_type="image")
    qm = QuestionMedia(question_id=q.id, media_type="image", file_url=q_image.file_url, upload_id=q_image.id)
    pg_session.add(qm)
    audio = _upload(pg_session, admin)
    pg_session.commit()

    ah = _headers(client, admin)
    added = client.post(f"/api/v1/tests/question-groups/{group.id}/media", json={"upload_id": str(audio.id)}, headers=ah)
    assert added.status_code == 201, added.json()
    gm_id = added.json()["data"]["id"]

    sh = _headers(client, student)
    attempt_id = client.post("/api/v1/attempts/start", json={"test_id": str(test.id)}, headers=sh).json()["data"]["id"]
    detail = client.get(f"/api/v1/attempts/{attempt_id}", headers=sh)
    assert detail.status_code == 200
    question = detail.json()["data"]["questions"][0]
    assert question["group_media"] == [{"id": gm_id, "media_type": "audio"}]
    assert question["media"] == [{"id": str(qm.id), "media_type": "image", "option_id": None}]
    assert audio.file_url not in detail.text and str(audio.id) not in detail.text

    group_url = client.get(f"/api/v1/attempts/{attempt_id}/group-media/{gm_id}/view-url", headers=sh)
    assert group_url.status_code == 200, group_url.json()
    assert group_url.json()["data"] == {"view_url": f"https://signed.example.test/{audio.file_url}?expires=300", "media_type": "audio"}

    # Task 1 regression: question-level media still served by its own endpoint.
    q_url = client.get(f"/api/v1/attempts/{attempt_id}/media/{qm.id}/view-url", headers=sh)
    assert q_url.status_code == 200
    assert q_url.json()["data"]["view_url"].endswith(f"{q_image.file_url}?expires=300")

    # Answer saving and submission unaffected.
    opt = next(o["id"] for o in question["options"])
    assert client.patch(f"/api/v1/attempts/{attempt_id}/answer", json={"question_id": question["id"], "selected_option": opt}, headers=sh).status_code == 200

    # Another student and the admin get 404 on this attempt's media.
    for intruder_headers in (_headers(client, other), ah):
        assert client.get(f"/api/v1/attempts/{attempt_id}/group-media/{gm_id}/view-url", headers=intruder_headers).status_code == 404

    assert client.post(f"/api/v1/attempts/{attempt_id}/submit", headers=sh).status_code == 200
    after = client.get(f"/api/v1/attempts/{attempt_id}/group-media/{gm_id}/view-url", headers=sh)
    assert after.status_code == 409
