"""Unit tests for the Sprint 27 presigned (direct-to-R2) upload flow —
repositories and StorageBackend mocked, no real R2/filesystem needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.uploads.exceptions import (
    FileTooLargeException,
    LessonNotFoundException,
    LessonUploadNotPermittedException,
    UnsupportedFileTypeException,
    UploadNotFoundException,
    UploadNotReadyException,
)
from app.modules.uploads.service import UploadService
from app.modules.uploads.storage import PresignedUpload


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_lesson_repo():
    return MagicMock()


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.create_presigned_upload.return_value = PresignedUpload(
        url="https://r2.example.com/presigned-put", object_key="lessons/l1/video/abc.mp4",
        required_headers={"Content-Type": "video/mp4"},
    )
    storage.create_presigned_download.return_value = "https://r2.example.com/presigned-get"
    return storage


@pytest.fixture
def service(mock_repo, mock_storage, mock_lesson_repo):
    return UploadService(mock_repo, MagicMock(), MagicMock(), MagicMock(), mock_storage, mock_lesson_repo)


# --- create_presigned_session ---

def test_create_presigned_session_rejects_unsupported_type(service):
    with pytest.raises(UnsupportedFileTypeException):
        service.create_presigned_session("f.exe", "application/x-msdownload", 1000, uuid.uuid4(), "Student", None)


def test_create_presigned_session_rejects_oversized_file(service):
    """2 GB + 1 byte — genuinely over the Sprint 27 Amendment's raised
    video limit, matching MAX_SIZE_VIDEO exactly rather than a stale value."""
    with pytest.raises(FileTooLargeException):
        service.create_presigned_session("f.mp4", "video/mp4", 2 * 1024 * 1024 * 1024 + 1, uuid.uuid4(), "Teacher", None)


def test_create_presigned_session_allows_personal_upload_for_any_role(service, mock_storage):
    upload, presigned = service.create_presigned_session("f.jpg", "image/jpeg", 1000, uuid.uuid4(), "Student", None)
    assert presigned.url == "https://r2.example.com/presigned-put"
    assert upload.lesson_id is None
    assert upload.status == "pending"


def test_create_presigned_session_raises_404_for_nonexistent_lesson(service, mock_lesson_repo):
    mock_lesson_repo.get_by_id.return_value = None
    with pytest.raises(LessonNotFoundException):
        service.create_presigned_session("f.mp4", "video/mp4", 1000, uuid.uuid4(), "Teacher", uuid.uuid4())


def test_create_presigned_session_blocks_student_from_lesson_upload(service, mock_lesson_repo):
    """The critical RBAC test: matches Lessons' own write tier exactly
    (Admin, Super Admin, Teacher) — Student must be rejected."""
    mock_lesson_repo.get_by_id.return_value = MagicMock()
    with pytest.raises(LessonUploadNotPermittedException):
        service.create_presigned_session("f.mp4", "video/mp4", 1000, uuid.uuid4(), "Student", uuid.uuid4())


@pytest.mark.parametrize("role", ["Admin", "Super Admin", "Teacher"])
def test_create_presigned_session_allows_lesson_upload_for_permitted_roles(service, mock_lesson_repo, role):
    mock_lesson_repo.get_by_id.return_value = MagicMock()
    lesson_id = uuid.uuid4()
    upload, _ = service.create_presigned_session("f.mp4", "video/mp4", 1000, uuid.uuid4(), role, lesson_id)
    assert upload.lesson_id == lesson_id


def test_create_presigned_session_builds_object_key_with_no_user_input(service, mock_lesson_repo, mock_storage):
    """The object key passed to the storage backend must never contain
    the raw, attacker-controlled original_filename."""
    mock_lesson_repo.get_by_id.return_value = MagicMock()
    lesson_id = uuid.uuid4()
    service.create_presigned_session("../../etc/passwd.mp4", "video/mp4", 1000, uuid.uuid4(), "Admin", lesson_id)
    called_key = mock_storage.create_presigned_upload.call_args[0][0]
    assert "../" not in called_key
    assert "passwd" not in called_key
    assert str(lesson_id) in called_key


# --- finalize_upload ---

def test_finalize_upload_flips_status_to_ready(service, mock_repo):
    user_id = uuid.uuid4()
    upload = MagicMock(user_id=user_id, status="pending")
    mock_repo.get_by_id.return_value = upload
    result = service.finalize_upload(upload.id, user_id=user_id)
    assert result.status == "ready"


def test_finalize_upload_raises_404_when_not_owned(service, mock_repo):
    upload = MagicMock(user_id=uuid.uuid4())
    mock_repo.get_by_id.return_value = upload
    with pytest.raises(UploadNotFoundException):
        service.finalize_upload(upload.id, user_id=uuid.uuid4())


# --- get_view_url ---

def test_get_view_url_returns_404_for_nonexistent_upload(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(UploadNotFoundException):
        service.get_view_url(uuid.uuid4(), user_id=uuid.uuid4())


def test_get_view_url_allows_any_authenticated_user_for_lesson_linked_media(service, mock_repo):
    """Lesson-linked media is authorized like the underlying Lesson
    itself (public GET) — NOT restricted to the uploader."""
    upload = MagicMock(user_id=uuid.uuid4(), lesson_id=uuid.uuid4(), status="ready")
    mock_repo.get_by_id.return_value = upload
    url = service.get_view_url(upload.id, user_id=uuid.uuid4())  # a DIFFERENT user than the uploader
    assert url == "https://r2.example.com/presigned-get"


def test_get_view_url_blocks_non_owner_for_personal_upload(service, mock_repo):
    upload = MagicMock(user_id=uuid.uuid4(), lesson_id=None, status="ready")
    mock_repo.get_by_id.return_value = upload
    with pytest.raises(UploadNotFoundException):
        service.get_view_url(upload.id, user_id=uuid.uuid4())


def test_get_view_url_raises_409_when_not_yet_finalized(service, mock_repo):
    user_id = uuid.uuid4()
    upload = MagicMock(user_id=user_id, lesson_id=None, status="pending")
    mock_repo.get_by_id.return_value = upload
    with pytest.raises(UploadNotReadyException):
        service.get_view_url(upload.id, user_id=user_id)
