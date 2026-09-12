"""Sprint 35 — Lesson.video_upload_id tests. Reuses the existing
test_lesson_service.py fixture pattern exactly (same MagicMock-based
repository mocking, no real DB)."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.lessons.exceptions import EmptyLessonContentException
from app.modules.lessons.schemas import LessonUpdateRequest
from app.modules.lessons.service import LessonService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_topic_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_topic_repo):
    return LessonService(mock_repo, mock_topic_repo)


def test_lesson_with_null_video_upload_id_is_unaffected(service, mock_repo):
    """Backward compatibility — a lesson with only the legacy `video`
    URL (video_upload_id=None) is not touched by anything Sprint 35 added."""
    lesson_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(
        id=lesson_id, video="https://old-video-url.example.com/x.mp4", video_upload_id=None, pdf=None, content=None,
    )
    service.update_lesson(lesson_id, LessonUpdateRequest(title="Yangilangan nom"), actor_id=uuid.uuid4())
    mock_repo.update.assert_called_once()


def test_schema_accepts_video_upload_id(service, mock_repo):
    lesson_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=lesson_id, video=None, video_upload_id=None, pdf=None, content="Matn bor")

    service.update_lesson(lesson_id, LessonUpdateRequest(video_upload_id=upload_id), actor_id=uuid.uuid4())

    updates_passed = mock_repo.update.call_args[0][1]
    assert updates_passed["video_upload_id"] == upload_id


def test_update_changes_video_upload_id_to_a_new_value(service, mock_repo):
    lesson_id = uuid.uuid4()
    old_upload_id = uuid.uuid4()
    new_upload_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=lesson_id, video=None, video_upload_id=old_upload_id, pdf=None, content="Matn")

    service.update_lesson(lesson_id, LessonUpdateRequest(video_upload_id=new_upload_id), actor_id=uuid.uuid4())

    updates_passed = mock_repo.update.call_args[0][1]
    assert updates_passed["video_upload_id"] == new_upload_id


def test_lesson_with_only_video_upload_id_is_not_treated_as_empty(service, mock_repo):
    """The exact Sprint 35 fix to _reject_if_would_leave_empty_content —
    a lesson whose ONLY content is an R2 video (no legacy `video` URL,
    no pdf, no content) must not be incorrectly rejected."""
    lesson_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=lesson_id, video=None, video_upload_id=None, pdf=None, content=None)

    upload_id = uuid.uuid4()
    # Should NOT raise — setting video_upload_id alone is real content.
    service.update_lesson(lesson_id, LessonUpdateRequest(video_upload_id=upload_id), actor_id=uuid.uuid4())
    mock_repo.update.assert_called_once()


def test_clearing_video_upload_id_with_no_other_content_is_rejected(service, mock_repo):
    lesson_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(
        id=lesson_id, video=None, video_upload_id=uuid.uuid4(), pdf=None, content=None,
    )
    with pytest.raises(EmptyLessonContentException):
        service.update_lesson(lesson_id, LessonUpdateRequest(video_upload_id=None), actor_id=uuid.uuid4())


def test_both_video_and_video_upload_id_can_coexist_without_error(service, mock_repo):
    """Neither field requires the other to be absent — the priority
    rule (R2 wins when both are present) is a FRONTEND display concern,
    not a backend validation rule."""
    lesson_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(
        id=lesson_id, video="https://legacy.example.com/old.mp4", video_upload_id=uuid.uuid4(), pdf=None, content=None,
    )
    service.update_lesson(lesson_id, LessonUpdateRequest(title="Ism"), actor_id=uuid.uuid4())
    mock_repo.update.assert_called_once()
