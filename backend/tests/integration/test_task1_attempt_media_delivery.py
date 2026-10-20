"""
Task 1 (IELTS/SAT/GRE audit) — question and option media delivered to
students during an exam attempt, against real PostgreSQL.

Covers:
- serialization: QuestionForAttemptOut.media carries only id/media_type/
  option_id (never file_url, upload_id or the storage object key), for
  every allowed media type, in attach order;
- missing / deleted media and media on a deleted option are not delivered;
- GET /attempts/{id}/media/{media_id}/view-url authorization: owner only,
  active attempts only, delivery-scope only (another test's media, a
  not-yet-routed module's media), upload readiness, storage that cannot
  sign, legacy external URLs;
- the real HTTP route with an overridden StorageBackend (no R2 needed).

Question-group media is NOT covered: QuestionGroup has no media relation
in the current schema (see the Task 1 report for the proposed migration).
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

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
from app.modules.tests.models import ExamModule, ExamSection, Test
from app.modules.tests.repository import ExamModuleRepository, ExamSectionRepository, QuestionGroupRepository, TestRepository
from app.modules.uploads.constants import UPLOAD_STATUS_READY
from app.modules.uploads.dependencies import get_storage_backend
from app.modules.uploads.models import Upload
from app.modules.uploads.repository import UploadRepository
from app.modules.uploads.storage import LocalDiskStorage, StorageBackend
from app.modules.users.models import User, UserStatus

PASSWORD = "Integration-T3st-P@ss1"


class FakeSigningStorage(StorageBackend):
    """Stands in for R2Storage: signs object keys without network access.
    Records the TTL it was asked for so the test can prove the short-lived
    uploads TTL is reused."""

    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def save(self, filename, stream):  # pragma: no cover - not used
        raise NotImplementedError

    def delete(self, file_url):  # pragma: no cover - not used
        raise NotImplementedError

    def read(self, file_url):  # pragma: no cover - not used
        raise NotImplementedError

    def create_presigned_download(self, object_key: str, expires_in: int) -> str:
        self.calls.append((object_key, expires_in))
        return f"https://signed.example.test/{object_key}?expires={expires_in}"


# --- helpers ----------------------------------------------------------------

def _make_user(pg_session, role_name: str = "Student") -> User:
    role = pg_session.query(Role).filter(Role.name == role_name).one()
    user = User(
        role_id=role.id, first_name="Media", last_name=role_name,
        email=f"media-{role_name.lower().replace(' ', '-')}-{uuid.uuid4()}@example.com",
        password_hash=PasswordService().hash_password(PASSWORD), status=UserStatus.ACTIVE,
    )
    pg_session.add(user)
    pg_session.flush()
    return user


def _make_test(pg_session) -> Test:
    subject = Subject(name=f"Media S-{uuid.uuid4()}")
    pg_session.add(subject)
    pg_session.flush()
    test = Test(subject_id=subject.id, title="Media test", duration=60, question_count=0, status="published",
                shuffle_questions=False, shuffle_answers=False)
    pg_session.add(test)
    pg_session.flush()
    return test


def _make_question(pg_session, test_id, module_id=None, text="Q") -> Question:
    q = Question(test_id=test_id, question_text=text, question_type="single_choice", score=1, module_id=module_id)
    pg_session.add(q)
    pg_session.flush()
    pg_session.add_all([
        QuestionOption(question_id=q.id, option_text="A", is_correct=True),
        QuestionOption(question_id=q.id, option_text="B", is_correct=False),
    ])
    pg_session.flush()
    pg_session.refresh(q)
    return q


def _make_upload(pg_session, owner: User, file_type="audio", status=UPLOAD_STATUS_READY) -> Upload:
    upload = Upload(user_id=owner.id, file_name="listening.mp3", file_url=f"private/{file_type}/{uuid.uuid4()}.mp3",
                    file_type=file_type, size_bytes=1024, status=status)
    pg_session.add(upload)
    pg_session.flush()
    return upload


def _make_media(pg_session, question, media_type="image", upload=None, option_id=None,
                file_url="https://cdn.example.test/legacy.png", created_at=None) -> QuestionMedia:
    m = QuestionMedia(
        question_id=question.id, option_id=option_id, media_type=media_type,
        file_url=upload.file_url if upload is not None else file_url,
        upload_id=upload.id if upload is not None else None,
    )
    if created_at is not None:
        m.created_at = created_at
    pg_session.add(m)
    pg_session.flush()
    return m


def _service(pg_session, storage: StorageBackend | None = None, with_media: bool = True) -> AttemptService:
    return AttemptService(
        AttemptRepository(pg_session), AnswerRepository(pg_session), TestRepository(pg_session),
        QuestionRepository(pg_session), OptionRepository(pg_session),
        ModuleExecutionService(
            ExamModuleRepository(pg_session), AttemptModuleProgressRepository(pg_session),
            QuestionRepository(pg_session), AnswerRepository(pg_session), AttemptRepository(pg_session),
        ),
        ExamModuleRepository(pg_session), ExamSectionRepository(pg_session), QuestionGroupRepository(pg_session),
        None,
        MediaRepository(pg_session) if with_media else None,
        UploadRepository(pg_session) if with_media else None,
        storage,
    )


def _start(pg_session, service, test, student):
    attempt = service.start_attempt(test.id, student.id)
    pg_session.commit()
    return attempt


# --- serialization ------------------------------------------------------------

def test_question_without_media_has_empty_media_list(pg_session):
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    _make_question(pg_session, test.id)
    pg_session.commit()
    service = _service(pg_session)
    attempt = _start(pg_session, service, test, student)

    detail = service.get_attempt_detail(attempt.id, student.id)
    assert detail.questions[0].media == []


def test_all_allowed_media_types_are_serialized_in_attach_order_without_urls(pg_session):
    admin = _make_user(pg_session, "Admin")
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    base = datetime.now(timezone.utc)
    upload = _make_upload(pg_session, admin)
    created = [
        _make_media(pg_session, q, "image", created_at=base),
        _make_media(pg_session, q, "audio", upload=upload, created_at=base + timedelta(seconds=1)),
        _make_media(pg_session, q, "video", created_at=base + timedelta(seconds=2)),
        _make_media(pg_session, q, "formula", created_at=base + timedelta(seconds=3)),
    ]
    pg_session.commit()
    service = _service(pg_session)
    attempt = _start(pg_session, service, test, student)

    media = service.get_attempt_detail(attempt.id, student.id).questions[0].media
    assert [m.id for m in media] == [m.id for m in created]
    assert [m.media_type for m in media] == ["image", "audio", "video", "formula"]
    dumped = [m.model_dump() for m in media]
    for d in dumped:
        assert set(d) == {"id", "media_type", "option_id"}
    assert upload.file_url not in str(dumped)


def test_option_media_is_serialized_with_option_id(pg_session):
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    option = q.options[0]
    m = _make_media(pg_session, q, "image", option_id=option.id)
    pg_session.commit()
    service = _service(pg_session)
    attempt = _start(pg_session, service, test, student)

    media = service.get_attempt_detail(attempt.id, student.id).questions[0].media
    assert len(media) == 1 and media[0].id == m.id and media[0].option_id == option.id


def test_deleted_media_and_media_on_deleted_option_are_not_delivered(pg_session):
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    deleted = _make_media(pg_session, q, "image")
    deleted.deleted_at = datetime.now(timezone.utc)
    option = q.options[1]
    on_deleted_option = _make_media(pg_session, q, "image", option_id=option.id)
    option.deleted_at = datetime.now(timezone.utc)
    kept = _make_media(pg_session, q, "audio")
    pg_session.commit()
    service = _service(pg_session)
    attempt = _start(pg_session, service, test, student)

    media = service.get_attempt_detail(attempt.id, student.id).questions[0].media
    assert [m.id for m in media] == [kept.id]

    for hidden in (deleted, on_deleted_option):
        with pytest.raises(AttemptMediaNotFoundException):
            service.get_media_view_url(attempt.id, hidden.id, student.id)


def test_service_without_media_repository_keeps_pre_task1_payload(pg_session):
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    _make_media(pg_session, q, "image")
    pg_session.commit()
    service = _service(pg_session, with_media=False)
    attempt = _start(pg_session, service, test, student)

    assert service.get_attempt_detail(attempt.id, student.id).questions[0].media == []


# --- view-url authorization -------------------------------------------------

def test_upload_backed_media_returns_short_lived_signed_url(pg_session):
    admin = _make_user(pg_session, "Admin")
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    upload = _make_upload(pg_session, admin)
    m = _make_media(pg_session, q, "audio", upload=upload)
    pg_session.commit()
    storage = FakeSigningStorage()
    service = _service(pg_session, storage=storage)
    attempt = _start(pg_session, service, test, student)

    out = service.get_media_view_url(attempt.id, m.id, student.id)
    assert out.media_type == "audio"
    assert out.view_url.startswith("https://signed.example.test/")
    assert storage.calls == [(upload.file_url, 300)]


def test_legacy_external_url_media_returns_stored_url(pg_session):
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    m = _make_media(pg_session, q, "image", file_url="https://cdn.example.test/diagram.png")
    pg_session.commit()
    storage = FakeSigningStorage()
    service = _service(pg_session, storage=storage)
    attempt = _start(pg_session, service, test, student)

    out = service.get_media_view_url(attempt.id, m.id, student.id)
    assert out.view_url == "https://cdn.example.test/diagram.png"
    assert storage.calls == []


def test_other_students_attempt_is_not_found(pg_session):
    owner = _make_user(pg_session)
    intruder = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    m = _make_media(pg_session, q, "image")
    pg_session.commit()
    service = _service(pg_session, storage=FakeSigningStorage())
    attempt = _start(pg_session, service, test, owner)

    with pytest.raises(AttemptNotFoundException):
        service.get_media_view_url(attempt.id, m.id, intruder.id)


def test_media_of_another_test_is_not_found(pg_session):
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    _make_question(pg_session, test.id)
    other_test = _make_test(pg_session)
    other_q = _make_question(pg_session, other_test.id)
    foreign = _make_media(pg_session, other_q, "image")
    pg_session.commit()
    service = _service(pg_session, storage=FakeSigningStorage())
    attempt = _start(pg_session, service, test, student)

    with pytest.raises(AttemptMediaNotFoundException):
        service.get_media_view_url(attempt.id, foreign.id, student.id)


def test_nonexistent_media_is_not_found(pg_session):
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    _make_question(pg_session, test.id)
    pg_session.commit()
    service = _service(pg_session, storage=FakeSigningStorage())
    attempt = _start(pg_session, service, test, student)

    with pytest.raises(AttemptMediaNotFoundException):
        service.get_media_view_url(attempt.id, uuid.uuid4(), student.id)


def test_media_of_not_yet_routed_module_is_hidden(pg_session):
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    section = ExamSection(test_id=test.id, name="Listening", order_number=0)
    pg_session.add(section)
    pg_session.flush()
    m1 = ExamModule(section_id=section.id, name="Part 1", order_number=0)
    m2 = ExamModule(section_id=section.id, name="Part 2", order_number=1)
    pg_session.add_all([m1, m2])
    pg_session.flush()
    q1 = _make_question(pg_session, test.id, module_id=m1.id, text="Q1")
    q2 = _make_question(pg_session, test.id, module_id=m2.id, text="Q2")
    current = _make_media(pg_session, q1, "audio")
    future = _make_media(pg_session, q2, "audio")
    pg_session.commit()
    service = _service(pg_session, storage=FakeSigningStorage())
    attempt = _start(pg_session, service, test, student)

    detail = service.get_attempt_detail(attempt.id, student.id)
    delivered = {m.id for q in detail.questions for m in q.media}
    assert delivered == {current.id}
    assert service.get_media_view_url(attempt.id, current.id, student.id).view_url
    with pytest.raises(AttemptMediaNotFoundException):
        service.get_media_view_url(attempt.id, future.id, student.id)


def test_finished_attempt_cannot_fetch_media(pg_session):
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    m = _make_media(pg_session, q, "image")
    pg_session.commit()
    service = _service(pg_session, storage=FakeSigningStorage())
    attempt = _start(pg_session, service, test, student)
    service.submit_attempt(attempt.id, student.id)
    pg_session.commit()

    with pytest.raises(AttemptNotActiveException):
        service.get_media_view_url(attempt.id, m.id, student.id)


def test_expired_attempt_is_lazily_finished_and_media_denied(pg_session):
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    m = _make_media(pg_session, q, "image")
    pg_session.commit()
    service = _service(pg_session, storage=FakeSigningStorage())
    attempt = _start(pg_session, service, test, student)
    attempt.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    pg_session.commit()

    with pytest.raises(AttemptNotActiveException):
        service.get_media_view_url(attempt.id, m.id, student.id)


def test_unfinalized_upload_is_unavailable(pg_session):
    admin = _make_user(pg_session, "Admin")
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    upload = _make_upload(pg_session, admin, status="pending")
    m = _make_media(pg_session, q, "audio", upload=upload)
    pg_session.commit()
    service = _service(pg_session, storage=FakeSigningStorage())
    attempt = _start(pg_session, service, test, student)

    with pytest.raises(AttemptMediaUnavailableException):
        service.get_media_view_url(attempt.id, m.id, student.id)


def test_deleted_upload_is_not_found(pg_session):
    admin = _make_user(pg_session, "Admin")
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    upload = _make_upload(pg_session, admin)
    m = _make_media(pg_session, q, "audio", upload=upload)
    upload.deleted_at = datetime.now(timezone.utc)
    pg_session.commit()
    service = _service(pg_session, storage=FakeSigningStorage())
    attempt = _start(pg_session, service, test, student)

    with pytest.raises(AttemptMediaNotFoundException):
        service.get_media_view_url(attempt.id, m.id, student.id)


def test_local_storage_without_presign_support_is_unavailable(pg_session, tmp_path):
    admin = _make_user(pg_session, "Admin")
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    upload = _make_upload(pg_session, admin)
    m = _make_media(pg_session, q, "audio", upload=upload)
    pg_session.commit()
    service = _service(pg_session, storage=LocalDiskStorage(base_dir=str(tmp_path)))
    attempt = _start(pg_session, service, test, student)

    with pytest.raises(AttemptMediaUnavailableException):
        service.get_media_view_url(attempt.id, m.id, student.id)


# --- real HTTP route ----------------------------------------------------------

@pytest.fixture
def signing_storage():
    storage = FakeSigningStorage()
    app.dependency_overrides[get_storage_backend] = lambda: storage
    try:
        yield storage
    finally:
        app.dependency_overrides.pop(get_storage_backend, None)


def _token(client, user: User) -> dict:
    login = client.post("/api/v1/auth/login", json={"identifier": user.email, "password": PASSWORD})
    assert login.status_code == 200, login.json()
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}


def test_http_detail_and_view_url_end_to_end(client, pg_session, signing_storage):
    admin = _make_user(pg_session, "Admin")
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    upload = _make_upload(pg_session, admin)
    m = _make_media(pg_session, q, "audio", upload=upload)
    pg_session.commit()
    headers = _token(client, student)

    start = client.post("/api/v1/attempts/start", json={"test_id": str(test.id)}, headers=headers)
    assert start.status_code == 201, start.json()
    attempt_id = start.json()["data"]["id"]

    detail = client.get(f"/api/v1/attempts/{attempt_id}", headers=headers)
    assert detail.status_code == 200
    media = detail.json()["data"]["questions"][0]["media"]
    assert media == [{"id": str(m.id), "media_type": "audio", "option_id": None}]
    assert upload.file_url not in detail.text

    view = client.get(f"/api/v1/attempts/{attempt_id}/media/{m.id}/view-url", headers=headers)
    assert view.status_code == 200, view.json()
    assert view.json()["data"]["media_type"] == "audio"
    assert view.json()["data"]["view_url"].startswith("https://signed.example.test/")


def test_http_requires_authentication(client, pg_session):
    response = client.get(f"/api/v1/attempts/{uuid.uuid4()}/media/{uuid.uuid4()}/view-url")
    assert response.status_code == 401


def test_http_other_user_gets_404_and_admin_has_no_bypass(client, pg_session, signing_storage):
    owner = _make_user(pg_session)
    other = _make_user(pg_session)
    admin = _make_user(pg_session, "Admin")
    test = _make_test(pg_session)
    q = _make_question(pg_session, test.id)
    m = _make_media(pg_session, q, "image")
    pg_session.commit()

    start = client.post("/api/v1/attempts/start", json={"test_id": str(test.id)}, headers=_token(client, owner))
    attempt_id = start.json()["data"]["id"]

    for intruder in (other, admin):
        response = client.get(f"/api/v1/attempts/{attempt_id}/media/{m.id}/view-url", headers=_token(client, intruder))
        assert response.status_code == 404
        assert response.json()["errors"] is not None


def test_http_foreign_media_returns_404_with_error_code(client, pg_session, signing_storage):
    student = _make_user(pg_session)
    test = _make_test(pg_session)
    _make_question(pg_session, test.id)
    other_test = _make_test(pg_session)
    foreign = _make_media(pg_session, _make_question(pg_session, other_test.id), "image")
    pg_session.commit()
    headers = _token(client, student)
    attempt_id = client.post("/api/v1/attempts/start", json={"test_id": str(test.id)}, headers=headers).json()["data"]["id"]

    response = client.get(f"/api/v1/attempts/{attempt_id}/media/{foreign.id}/view-url", headers=headers)
    assert response.status_code == 404
    assert response.json()["success"] is False
