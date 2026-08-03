"""Unit tests for UploadService — repositories and StorageBackend
mocked, no real filesystem or DB needed."""
import io
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.uploads.exceptions import FileTooLargeException, UnsupportedFileTypeException, UploadNotFoundException
from app.modules.uploads.service import UploadService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_image_repo():
    return MagicMock()


@pytest.fixture
def mock_video_repo():
    return MagicMock()


@pytest.fixture
def mock_document_repo():
    return MagicMock()


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.save.return_value = "storage/uploads/generated-name.png"
    return storage


@pytest.fixture
def service(mock_repo, mock_image_repo, mock_video_repo, mock_document_repo, mock_storage):
    return UploadService(mock_repo, mock_image_repo, mock_video_repo, mock_document_repo, mock_storage)


def test_upload_rejects_unsupported_type(service):
    with pytest.raises(UnsupportedFileTypeException):
        service.upload(io.BytesIO(b"data"), "virus.exe", "application/x-executable", 100, user_id=uuid.uuid4())


def test_upload_rejects_oversized_image(service):
    oversized = 11 * 1024 * 1024  # 11 MB > 10 MB image limit
    with pytest.raises(FileTooLargeException):
        service.upload(io.BytesIO(b"data"), "photo.png", "image/png", oversized, user_id=uuid.uuid4())


def test_upload_succeeds_and_creates_image_metadata(service, mock_repo, mock_image_repo, mock_storage):
    upload = service.upload(io.BytesIO(b"data"), "photo.png", "image/png", 1024, user_id=uuid.uuid4())
    mock_repo.create.assert_called_once()
    mock_image_repo.create.assert_called_once()
    mock_storage.save.assert_called_once()
    assert upload.file_type == "image"


def test_upload_uses_generated_uuid_name_not_original_filename(service, mock_storage):
    """The most important security property of this module: the on-disk
    filename must never be derived from user input."""
    service.upload(io.BytesIO(b"data"), "../../etc/passwd.png", "image/png", 1024, user_id=uuid.uuid4())
    saved_name = mock_storage.save.call_args[0][0]
    assert "../" not in saved_name
    assert "etc" not in saved_name


def test_upload_video_creates_video_metadata_with_null_duration(service, mock_video_repo):
    service.upload(io.BytesIO(b"data"), "clip.mp4", "video/mp4", 1024, user_id=uuid.uuid4())
    created_video = mock_video_repo.create.call_args[0][0]
    assert created_video.duration_seconds is None  # approved scope boundary, not a bug


def test_upload_document_creates_document_metadata_with_null_page_count(service, mock_document_repo):
    service.upload(io.BytesIO(b"data"), "report.pdf", "application/pdf", 1024, user_id=uuid.uuid4())
    created_doc = mock_document_repo.create.call_args[0][0]
    assert created_doc.page_count is None  # approved scope boundary, not a bug


def test_upload_audio_creates_no_metadata_row(service, mock_image_repo, mock_video_repo, mock_document_repo):
    service.upload(io.BytesIO(b"data"), "song.mp3", "audio/mpeg", 1024, user_id=uuid.uuid4())
    mock_image_repo.create.assert_not_called()
    mock_video_repo.create.assert_not_called()
    mock_document_repo.create.assert_not_called()


def test_get_raises_when_not_owned(service, mock_repo):
    mock_repo.get_by_id.return_value = MagicMock(user_id=uuid.uuid4())
    with pytest.raises(UploadNotFoundException):
        service.get(uuid.uuid4(), user_id=uuid.uuid4())


def test_delete_removes_physical_file_and_soft_deletes_row(service, mock_repo, mock_storage):
    user_id = uuid.uuid4()
    upload = MagicMock(user_id=user_id, file_url="storage/uploads/x.png")
    mock_repo.get_by_id.return_value = upload
    service.delete(upload.id, user_id=user_id)
    mock_storage.delete.assert_called_once_with("storage/uploads/x.png")
    mock_repo.soft_delete.assert_called_once_with(upload)
