"""Unit tests for the Sprint 27 Amendment — R2 Multipart Upload (2 GB
video support). Repositories and StorageBackend mocked, no real R2/DB
needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.uploads.constants import MULTIPART_MAX_PART_NUMBER, MULTIPART_PART_SIZE_BYTES
from app.modules.uploads.exceptions import (
    FileTooLargeException,
    InvalidPartNumberException,
    LessonNotFoundException,
    LessonUploadNotPermittedException,
    MissingPartsException,
    NotAMultipartUploadException,
    UnsupportedFileTypeException,
    UploadNotFoundException,
)
from app.modules.uploads.service import UploadService

GB = 1024 * 1024 * 1024


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_lesson_repo():
    return MagicMock()


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.create_multipart_upload.return_value = "r2-multipart-abc123"
    storage.create_presigned_part_url.return_value = "https://r2.example.com/presigned-part"
    return storage


@pytest.fixture
def service(mock_repo, mock_storage, mock_lesson_repo):
    return UploadService(mock_repo, MagicMock(), MagicMock(), MagicMock(), mock_storage, mock_lesson_repo)


# --- initiate_multipart_upload ---

def test_initiate_rejects_unsupported_type(service):
    with pytest.raises(UnsupportedFileTypeException):
        service.initiate_multipart_upload("f.exe", "application/x-msdownload", 1 * GB, uuid.uuid4(), "Teacher", None)


def test_initiate_rejects_file_over_2gb(service):
    with pytest.raises(FileTooLargeException):
        service.initiate_multipart_upload("f.mp4", "video/mp4", 2 * GB + 1, uuid.uuid4(), "Teacher", None)


def test_initiate_accepts_file_at_exactly_2gb(service, mock_storage):
    upload, multipart_id, total_parts = service.initiate_multipart_upload(
        "f.mp4", "video/mp4", 2 * GB, uuid.uuid4(), "Teacher", None,
    )
    assert multipart_id == "r2-multipart-abc123"
    assert upload.multipart_upload_id == "r2-multipart-abc123"
    assert upload.status == "pending"


def test_initiate_computes_correct_total_parts(service):
    # 45 MB file, 20 MB parts -> ceil(45/20) = 3 parts
    _, _, total_parts = service.initiate_multipart_upload(
        "f.mp4", "video/mp4", 45 * 1024 * 1024, uuid.uuid4(), "Teacher", None,
    )
    assert total_parts == 3


def test_initiate_2gb_file_stays_within_s3_part_limit(service):
    """The real headroom check: even at the 2 GB ceiling with our
    chosen part size, we never come close to S3/R2's 10,000-part cap."""
    _, _, total_parts = service.initiate_multipart_upload(
        "f.mp4", "video/mp4", 2 * GB, uuid.uuid4(), "Teacher", None,
    )
    assert total_parts < MULTIPART_MAX_PART_NUMBER
    assert total_parts == -(-2 * GB // MULTIPART_PART_SIZE_BYTES)  # ceiling division, matches the service's own math


def test_initiate_raises_404_for_nonexistent_lesson(service, mock_lesson_repo):
    mock_lesson_repo.get_by_id.return_value = None
    with pytest.raises(LessonNotFoundException):
        service.initiate_multipart_upload("f.mp4", "video/mp4", 1 * GB, uuid.uuid4(), "Teacher", uuid.uuid4())


def test_initiate_blocks_student_from_lesson_upload(service, mock_lesson_repo):
    mock_lesson_repo.get_by_id.return_value = MagicMock()
    with pytest.raises(LessonUploadNotPermittedException):
        service.initiate_multipart_upload("f.mp4", "video/mp4", 1 * GB, uuid.uuid4(), "Student", uuid.uuid4())


@pytest.mark.parametrize("role", ["Admin", "Super Admin", "Teacher"])
def test_initiate_allows_lesson_upload_for_permitted_roles(service, mock_lesson_repo, role):
    mock_lesson_repo.get_by_id.return_value = MagicMock()
    upload, _, _ = service.initiate_multipart_upload("f.mp4", "video/mp4", 1 * GB, uuid.uuid4(), role, uuid.uuid4())
    assert upload.status == "pending"


def test_initiate_never_persists_a_presigned_url(service, mock_repo):
    """The Upload row must only ever get an object key + R2's own
    multipart ID — never a presigned URL (explicit instruction: never
    persist presigned URLs in PostgreSQL)."""
    service.initiate_multipart_upload("f.mp4", "video/mp4", 1 * GB, uuid.uuid4(), "Teacher", None)
    created_upload = mock_repo.create.call_args[0][0]
    assert "https://" not in created_upload.file_url
    assert created_upload.multipart_upload_id == "r2-multipart-abc123"


# --- get_part_upload_url ---

def test_get_part_url_rejects_part_number_zero(service, mock_repo):
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id="mp1")
    mock_repo.get_by_id.return_value = upload
    with pytest.raises(InvalidPartNumberException):
        service.get_part_upload_url(upload.id, user_id=upload.user_id, part_number=0)


def test_get_part_url_rejects_part_number_over_10000(service, mock_repo):
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id="mp1")
    mock_repo.get_by_id.return_value = upload
    with pytest.raises(InvalidPartNumberException):
        service.get_part_upload_url(upload.id, user_id=upload.user_id, part_number=10001)


def test_get_part_url_returns_404_for_nonowned_upload(service, mock_repo):
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id="mp1")
    mock_repo.get_by_id.return_value = upload
    with pytest.raises(UploadNotFoundException):
        service.get_part_upload_url(upload.id, user_id=uuid.uuid4(), part_number=1)  # different user


def test_get_part_url_raises_409_when_not_a_multipart_upload(service, mock_repo):
    """The critical guard against arbitrary object-key/R2-upload-ID
    manipulation: an Upload row that was never a multipart session
    (multipart_upload_id is NULL) must be rejected, not silently
    treated as one."""
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id=None)
    mock_repo.get_by_id.return_value = upload
    with pytest.raises(NotAMultipartUploadException):
        service.get_part_upload_url(upload.id, user_id=upload.user_id, part_number=1)


def test_get_part_url_calls_storage_with_the_owned_uploads_own_key_and_multipart_id(service, mock_repo, mock_storage):
    """The object key and multipart ID always come from the server-side
    Upload row — never from anything the caller could supply."""
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id="mp1", file_url="lessons/l1/video/real-key.mp4")
    mock_repo.get_by_id.return_value = upload
    service.get_part_upload_url(upload.id, user_id=upload.user_id, part_number=5)
    mock_storage.create_presigned_part_url.assert_called_once_with(
        "lessons/l1/video/real-key.mp4", "mp1", 5, 15 * 60,
    )


# --- complete_multipart_upload ---

def test_complete_rejects_empty_parts_list(service, mock_repo):
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id="mp1")
    mock_repo.get_by_id.return_value = upload
    with pytest.raises(MissingPartsException):
        service.complete_multipart_upload(upload.id, user_id=upload.user_id, parts=[])


def test_complete_calls_storage_with_correctly_shaped_parts(service, mock_repo, mock_storage):
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id="mp1", file_url="key.mp4")
    mock_repo.get_by_id.return_value = upload
    service.complete_multipart_upload(upload.id, user_id=upload.user_id, parts=[(1, "etag1"), (2, "etag2")])
    mock_storage.complete_multipart_upload.assert_called_once_with(
        "key.mp4", "mp1", [{"PartNumber": 1, "ETag": "etag1"}, {"PartNumber": 2, "ETag": "etag2"}],
    )


def test_complete_flips_status_to_ready(service, mock_repo):
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id="mp1", file_url="key.mp4")
    mock_repo.get_by_id.return_value = upload
    result = service.complete_multipart_upload(upload.id, user_id=upload.user_id, parts=[(1, "etag1")])
    assert result.status == "ready"


def test_complete_rejects_unauthorized_user(service, mock_repo):
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id="mp1")
    mock_repo.get_by_id.return_value = upload
    with pytest.raises(UploadNotFoundException):
        service.complete_multipart_upload(upload.id, user_id=uuid.uuid4(), parts=[(1, "etag1")])


# --- abort_multipart_upload ---

def test_abort_calls_storage_abort_with_owned_keys(service, mock_repo, mock_storage):
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id="mp1", file_url="key.mp4")
    mock_repo.get_by_id.return_value = upload
    service.abort_multipart_upload(upload.id, user_id=upload.user_id)
    mock_storage.abort_multipart_upload.assert_called_once_with("key.mp4", "mp1")


def test_abort_marks_upload_failed_not_deleted(service, mock_repo):
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id="mp1", file_url="key.mp4")
    mock_repo.get_by_id.return_value = upload
    service.abort_multipart_upload(upload.id, user_id=upload.user_id)
    assert upload.status == "failed"


def test_abort_rejects_unauthorized_user(service, mock_repo, mock_storage):
    """Never abort another user's multipart session."""
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id="mp1")
    mock_repo.get_by_id.return_value = upload
    with pytest.raises(UploadNotFoundException):
        service.abort_multipart_upload(upload.id, user_id=uuid.uuid4())
    mock_storage.abort_multipart_upload.assert_not_called()


def test_abort_raises_409_when_not_a_multipart_upload(service, mock_repo):
    upload = MagicMock(user_id=uuid.uuid4(), multipart_upload_id=None)
    mock_repo.get_by_id.return_value = upload
    with pytest.raises(NotAMultipartUploadException):
        service.abort_multipart_upload(upload.id, user_id=upload.user_id)
