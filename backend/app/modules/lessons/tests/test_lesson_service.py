"""Unit tests for LessonService — repositories mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.lessons.exceptions import (
    DuplicateOrderNumberException,
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
    mock_repo.get_by_id.return_value = MagicMock(id=lesson_id, video=None, video_upload_id=None, pdf=None, content="Faqat matn bor edi")
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


# --- Sprint 38: Lesson Ordering ---

def test_create_without_order_number_auto_assigns_next_in_topic(service, mock_repo, mock_topic_repo):
    topic_id = uuid.uuid4()
    mock_topic_repo.get_by_id.return_value = MagicMock(id=topic_id)
    mock_repo.get_next_order_number.return_value = 3

    service.create_lesson(
        LessonCreateRequest(topic_id=topic_id, title="Yangi dars", content="Matn"), actor_id=uuid.uuid4(),
    )

    created_lesson = mock_repo.create.call_args[0][0]
    assert created_lesson.order_number == 3
    mock_repo.get_next_order_number.assert_called_once_with(topic_id)


def test_create_with_explicit_order_number_uses_it_and_skips_auto_assign(service, mock_repo, mock_topic_repo):
    topic_id = uuid.uuid4()
    mock_topic_repo.get_by_id.return_value = MagicMock(id=topic_id)

    service.create_lesson(
        LessonCreateRequest(topic_id=topic_id, title="Dars", content="Matn", order_number=7), actor_id=uuid.uuid4(),
    )

    created_lesson = mock_repo.create.call_args[0][0]
    assert created_lesson.order_number == 7
    mock_repo.get_next_order_number.assert_not_called()


def test_first_lesson_in_a_topic_gets_order_number_zero(service, mock_repo, mock_topic_repo):
    topic_id = uuid.uuid4()
    mock_topic_repo.get_by_id.return_value = MagicMock(id=topic_id)
    mock_repo.get_next_order_number.return_value = 0  # repository's own empty-topic case

    service.create_lesson(
        LessonCreateRequest(topic_id=topic_id, title="Birinchi dars", content="Matn"), actor_id=uuid.uuid4(),
    )
    assert mock_repo.create.call_args[0][0].order_number == 0


def test_create_rejects_negative_order_number_at_schema_level():
    with pytest.raises(ValueError):
        LessonCreateRequest(topic_id=uuid.uuid4(), title="Dars", content="Matn", order_number=-1)


def test_update_rejects_negative_order_number_at_schema_level():
    with pytest.raises(ValueError):
        LessonUpdateRequest(order_number=-1)


def test_create_duplicate_order_number_raises_conflict_not_silent_overwrite(service, mock_repo, mock_topic_repo):
    from sqlalchemy.exc import IntegrityError
    topic_id = uuid.uuid4()
    mock_topic_repo.get_by_id.return_value = MagicMock(id=topic_id)
    mock_repo.commit.side_effect = IntegrityError("stmt", {}, Exception("unique violation"))

    with pytest.raises(DuplicateOrderNumberException):
        service.create_lesson(
            LessonCreateRequest(topic_id=topic_id, title="Dars", content="Matn", order_number=2), actor_id=uuid.uuid4(),
        )
    mock_repo.db.rollback.assert_called_once()


def test_update_duplicate_order_number_raises_conflict(service, mock_repo):
    from sqlalchemy.exc import IntegrityError
    lesson = MagicMock(id=uuid.uuid4(), video="x", video_upload_id=None, pdf=None, content=None)
    mock_repo.get_by_id.return_value = lesson
    mock_repo.commit.side_effect = IntegrityError("stmt", {}, Exception("unique violation"))

    with pytest.raises(DuplicateOrderNumberException):
        service.update_lesson(lesson.id, LessonUpdateRequest(order_number=1), actor_id=uuid.uuid4())
    mock_repo.db.rollback.assert_called_once()


def test_update_order_number_alone_does_not_touch_content_fields(service, mock_repo):
    lesson = MagicMock(id=uuid.uuid4(), video="x", video_upload_id=None, pdf=None, content=None)
    mock_repo.get_by_id.return_value = lesson

    service.update_lesson(lesson.id, LessonUpdateRequest(order_number=5), actor_id=uuid.uuid4())

    updates_passed = mock_repo.update.call_args[0][1]
    assert updates_passed["order_number"] == 5
    assert "video" not in updates_passed
    assert "content" not in updates_passed


def test_omitting_order_number_on_update_leaves_it_unchanged(service, mock_repo):
    """exclude_unset=True — order_number simply isn't in the updates
    dict when the caller doesn't send it, so the existing value on the
    Lesson row is never touched."""
    lesson = MagicMock(id=uuid.uuid4(), video="x", video_upload_id=None, pdf=None, content=None, order_number=4)
    mock_repo.get_by_id.return_value = lesson

    service.update_lesson(lesson.id, LessonUpdateRequest(title="Yangi nom"), actor_id=uuid.uuid4())

    updates_passed = mock_repo.update.call_args[0][1]
    assert "order_number" not in updates_passed
