"""Sprint 29 — Critical fix tests. Real io.BytesIO streams are used
(not MagicMock) so the bounded chunked-read logic is genuinely
exercised, not just mock-call-asserted — this proves the actual memory
behavior, not merely that a constant exists."""
import io
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.uploads.constants import LEGACY_UPLOAD_MAX_VIDEO_SIZE, MAX_SIZE_VIDEO
from app.modules.uploads.exceptions import FileTooLargeException
from app.modules.uploads.service import UploadService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.save.return_value = "storage/uploads/generated-name.mp4"
    return storage


@pytest.fixture
def service(mock_repo, mock_storage):
    return UploadService(mock_repo, MagicMock(), MagicMock(), MagicMock(), mock_storage, MagicMock())


def test_legacy_small_video_is_accepted(service, mock_repo):
    """Scenario A — a real video well under the legacy limit succeeds normally."""
    small_video = io.BytesIO(b"x" * (1024 * 1024))  # 1 MB
    upload = service.upload(small_video, "clip.mp4", "video/mp4", 1024 * 1024, user_id=uuid.uuid4())
    assert upload.file_type == "video"
    mock_repo.create.assert_called_once()


def test_legacy_video_just_above_limit_is_rejected_by_declared_size(service, mock_repo, mock_storage):
    """Scenario B — declared size alone already exceeds the legacy
    limit; rejected via the fast-path check before any stream I/O."""
    stream = io.BytesIO(b"x" * 100)  # tiny real content — declared size is what's being tested here
    with pytest.raises(FileTooLargeException):
        service.upload(stream, "big.mp4", "video/mp4", LEGACY_UPLOAD_MAX_VIDEO_SIZE + 1, user_id=uuid.uuid4())
    mock_storage.save.assert_not_called()
    mock_repo.create.assert_not_called()


def test_legacy_video_exceeding_limit_in_actual_bytes_is_rejected_even_if_declared_size_lies(service, mock_repo, mock_storage):
    """Scenario C — the real defense-in-depth test: a client that LIES
    about the declared size (claims a small size but the real stream
    contains more than the legacy limit) is still caught by the
    bounded chunked read, which counts REAL bytes consumed — proving
    the fix does not merely trust the client-supplied size_bytes value."""
    real_oversized_content = b"x" * (LEGACY_UPLOAD_MAX_VIDEO_SIZE + 1024)  # 1 KB over the real limit
    lying_stream = io.BytesIO(real_oversized_content)
    with pytest.raises(FileTooLargeException):
        service.upload(lying_stream, "sneaky.mp4", "video/mp4", 1024, user_id=uuid.uuid4())  # declares only 1 KB
    mock_storage.save.assert_not_called()
    mock_repo.create.assert_not_called()


def test_bounded_read_never_materializes_more_than_one_chunk_at_once(service):
    """Verifies the actual chunking mechanism directly: a stream larger
    than the limit is read in bounded pieces, not via a single
    unbounded .read() call — spying on the stream's own .read() to
    confirm it is called with an explicit, bounded chunk size argument,
    never with no argument (which would mean 'read everything')."""
    real_oversized_content = b"x" * (LEGACY_UPLOAD_MAX_VIDEO_SIZE + 1024)
    stream = io.BytesIO(real_oversized_content)
    read_calls = []
    original_read = stream.read

    def spy_read(size=None):
        read_calls.append(size)
        return original_read(size)

    stream.read = spy_read

    with pytest.raises(FileTooLargeException):
        service.upload(stream, "sneaky.mp4", "video/mp4", 1024, user_id=uuid.uuid4())

    assert len(read_calls) > 0
    assert all(size is not None and size <= 1024 * 1024 for size in read_calls), (
        "every .read() call during the bounded check must pass an explicit, bounded chunk size — "
        "never an unbounded/whole-file read"
    )


def test_rejected_legacy_upload_creates_no_database_record(service, mock_repo):
    stream = io.BytesIO(b"x" * (LEGACY_UPLOAD_MAX_VIDEO_SIZE + 1))
    with pytest.raises(FileTooLargeException):
        service.upload(stream, "big.mp4", "video/mp4", 1, user_id=uuid.uuid4())
    mock_repo.create.assert_not_called()
    mock_repo.commit.assert_not_called()


def test_rejected_legacy_upload_never_touches_storage(service, mock_storage):
    """No orphaned local file / R2 object can result, since storage.save() is never reached."""
    stream = io.BytesIO(b"x" * (LEGACY_UPLOAD_MAX_VIDEO_SIZE + 1))
    with pytest.raises(FileTooLargeException):
        service.upload(stream, "big.mp4", "video/mp4", 1, user_id=uuid.uuid4())
    mock_storage.save.assert_not_called()


def test_legacy_video_limit_is_significantly_smaller_than_the_r2_limit():
    """Sanity check on the constants themselves — the legacy limit must
    remain meaningfully small, and MAX_SIZE_VIDEO (R2/multipart) must
    remain exactly 2 GB, unchanged by this fix."""
    assert LEGACY_UPLOAD_MAX_VIDEO_SIZE == 20 * 1024 * 1024
    assert MAX_SIZE_VIDEO == 2 * 1024 * 1024 * 1024
    assert LEGACY_UPLOAD_MAX_VIDEO_SIZE < MAX_SIZE_VIDEO


def test_legacy_image_upload_limit_is_unchanged_by_this_fix(service, mock_repo):
    """Scope check — non-video types must be completely unaffected."""
    valid_image = io.BytesIO(b"x" * 1024)
    upload = service.upload(valid_image, "photo.png", "image/png", 1024, user_id=uuid.uuid4())
    assert upload.file_type == "image"


def test_legacy_oversized_image_still_rejected_at_its_own_existing_limit(service):
    """Confirms image's own pre-existing 10 MB limit still applies
    exactly as before — no behavior change for this unrelated type."""
    oversized = 11 * 1024 * 1024
    with pytest.raises(FileTooLargeException):
        service.upload(io.BytesIO(b"x"), "photo.png", "image/png", oversized, user_id=uuid.uuid4())
