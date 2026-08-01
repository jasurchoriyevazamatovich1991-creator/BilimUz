"""Unit tests for TopicService — all three repositories mocked, no real DB."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.topics.exceptions import (
    InvalidGradeReferenceException,
    InvalidSubjectReferenceException,
    TopicNotFoundException,
)
from app.modules.topics.schemas import TopicCreateRequest, TopicUpdateRequest
from app.modules.topics.service import TopicService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_subject_repo():
    return MagicMock()


@pytest.fixture
def mock_grade_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_subject_repo, mock_grade_repo):
    return TopicService(mock_repo, mock_subject_repo, mock_grade_repo)


def test_create_rejects_nonexistent_subject(service, mock_subject_repo):
    mock_subject_repo.get_by_id.return_value = None
    data = TopicCreateRequest(subject_id=uuid.uuid4(), title="Algebra asoslari")
    with pytest.raises(InvalidSubjectReferenceException):
        service.create_topic(data, actor_id=uuid.uuid4())


def test_create_rejects_nonexistent_grade(service, mock_subject_repo, mock_grade_repo):
    mock_subject_repo.get_by_id.return_value = MagicMock()
    mock_grade_repo.get_by_id.return_value = None
    data = TopicCreateRequest(subject_id=uuid.uuid4(), grade_id=uuid.uuid4(), title="Algebra asoslari")
    with pytest.raises(InvalidGradeReferenceException):
        service.create_topic(data, actor_id=uuid.uuid4())


def test_create_succeeds_with_valid_references(service, mock_repo, mock_subject_repo, mock_grade_repo):
    mock_subject_repo.get_by_id.return_value = MagicMock()
    mock_grade_repo.get_by_id.return_value = MagicMock()
    data = TopicCreateRequest(subject_id=uuid.uuid4(), grade_id=uuid.uuid4(), title="Algebra asoslari", order_number=1)
    topic = service.create_topic(data, actor_id=uuid.uuid4())
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()
    assert topic.title == "Algebra asoslari"
    assert topic.order_number == 1


def test_create_without_grade_is_allowed(service, mock_repo, mock_subject_repo, mock_grade_repo):
    mock_subject_repo.get_by_id.return_value = MagicMock()
    data = TopicCreateRequest(subject_id=uuid.uuid4(), title="Geometriya")
    service.create_topic(data, actor_id=uuid.uuid4())
    mock_grade_repo.get_by_id.assert_not_called()  # grade check skipped when grade_id is None
    mock_repo.create.assert_called_once()


def test_get_topic_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(TopicNotFoundException):
        service.get_topic(uuid.uuid4())


def test_update_rejects_nonexistent_new_grade(service, mock_repo, mock_grade_repo):
    topic_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=topic_id)
    mock_grade_repo.get_by_id.return_value = None
    with pytest.raises(InvalidGradeReferenceException):
        service.update_topic(topic_id, TopicUpdateRequest(grade_id=uuid.uuid4()), actor_id=uuid.uuid4())


def test_delete_soft_deletes(service, mock_repo):
    topic = MagicMock()
    mock_repo.get_by_id.return_value = topic
    service.delete_topic(topic.id, actor_id=uuid.uuid4())
    mock_repo.soft_delete.assert_called_once_with(topic)
    mock_repo.commit.assert_called_once()


@pytest.mark.parametrize("order_number", [-1, -100])
def test_negative_order_number_rejected_by_schema(order_number):
    with pytest.raises(ValueError):
        TopicCreateRequest(subject_id=uuid.uuid4(), title="Test mavzu", order_number=order_number)
