"""Unit tests for LessonService — repositories mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.lessons.exceptions import (
    EmptyLessonContentException,
    InvalidTopicReferenceException,
    LessonNotFoundException,
)
from app.modules.lessons.schemas import LessonCreateRequest, LessonUpdateRequest
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


def test_create_rejects_nonexistent_topic(service, mock_topic_repo):
    mock_topic_repo.get_by_id.return_value = None
    data = LessonCreateRequest(topic_id=uuid.uuid4(), title="Kirish darsi", content="Matn")
    with pytest.raises(InvalidTopicReferenceException):
        service.create_lesson(data, actor_id=uuid.uuid4())


def test_create_succeeds_with_valid_topic(service, mock_repo, mock_topic_repo):
    mock_topic_repo.get_by_id.return_value = MagicMock()
    data = LessonCreateRequest(topic_id=uuid.uuid4(), title="Kirish darsi", video="https://example.com/v.mp4")
    lesson = service.create_lesson(data, actor_id=uuid.uuid4())
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()
    assert lesson.title == "Kirish darsi"


def test_schema_rejects_lesson_with_no_content_at_all():
    with pytest.raises(ValueError):
        LessonCreateRequest(topic_id=uuid.uuid4(), title="Bo'sh dars")


def test_schema_rejects_invalid_url_scheme():
    with pytest.raises(ValueError):
        LessonCreateRequest(topic_id=uuid.uuid4(), title="Dars", video="ftp://example.com/v.mp4")


def test_get_lesson_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(LessonNotFoundException):
        service.get_lesson(uuid.uuid4())


def test_update_rejects_clearing_all_content(service, mock_repo):
    lesson_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=lesson_id, video=None, pdf=None, content="Faqat matn bor edi")
    with pytest.raises(EmptyLessonContentException):
        service.update_lesson(lesson_id, LessonUpdateRequest(content=None), actor_id=uuid.uuid4())


def test_update_allows_swapping_content_types(service, mock_repo):
    """Clearing 'content' is fine as long as 'video' is being set in the
    same update — the merged final state still has content."""
    lesson_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=lesson_id, video=None, pdf=None, content="Eski matn")
    service.update_lesson(
        lesson_id,
        LessonUpdateRequest(content=None, video="https://example.com/new.mp4"),
        actor_id=uuid.uuid4(),
    )
    mock_repo.update.assert_called_once()


def test_delete_soft_deletes(service, mock_repo):
    lesson = MagicMock()
    mock_repo.get_by_id.return_value = lesson
    service.delete_lesson(lesson.id, actor_id=uuid.uuid4())
    mock_repo.soft_delete.assert_called_once_with(lesson)
    mock_repo.commit.assert_called_once()
