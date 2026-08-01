"""Unit tests for TestService — all repositories mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.tests.exceptions import (
    CannotPublishEmptyTestException,
    InvalidStatusTransitionException,
    InvalidTestReferenceException,
    TestNotFoundException,
)
from app.modules.tests.models import TestStatus
from app.modules.tests.schemas import TestCreateRequest, TestUpdateRequest
from app.modules.tests.service import TestService


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
def mock_topic_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_subject_repo, mock_grade_repo, mock_topic_repo):
    return TestService(mock_repo, mock_subject_repo, mock_grade_repo, mock_topic_repo)


def test_create_rejects_invalid_subject(service, mock_subject_repo):
    mock_subject_repo.get_by_id.return_value = None
    data = TestCreateRequest(subject_id=uuid.uuid4(), title="Matematika DTM")
    with pytest.raises(InvalidTestReferenceException):
        service.create_test(data, actor_id=uuid.uuid4())


def test_create_succeeds_with_no_references(service, mock_repo):
    """subject_id/grade_id/topic_id are all optional — a test can exist
    without being scoped to any of them."""
    data = TestCreateRequest(title="Umumiy test")
    test = service.create_test(data, actor_id=uuid.uuid4())
    mock_repo.create.assert_called_once()
    assert test.title == "Umumiy test"


def test_get_test_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(TestNotFoundException):
        service.get_test(uuid.uuid4())


def test_publish_rejects_empty_test(service, mock_repo):
    test_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=test_id, status=TestStatus.DRAFT.value, question_count=0)
    with pytest.raises(CannotPublishEmptyTestException):
        service.publish_test(test_id, actor_id=uuid.uuid4())


def test_publish_rejects_invalid_transition(service, mock_repo):
    """A test already archived can never be published again."""
    test_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=test_id, status=TestStatus.ARCHIVED.value, question_count=5)
    with pytest.raises(InvalidStatusTransitionException):
        service.publish_test(test_id, actor_id=uuid.uuid4())


def test_publish_succeeds_with_questions(service, mock_repo):
    test_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=test_id, status=TestStatus.DRAFT.value, question_count=3)
    service.publish_test(test_id, actor_id=uuid.uuid4())
    mock_repo.update.assert_called_once()
    called_updates = mock_repo.update.call_args[0][1]
    assert called_updates["status"] == "published"


def test_update_rejects_invalid_new_grade(service, mock_repo, mock_grade_repo):
    test_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=test_id, subject_id=None, grade_id=None, topic_id=None)
    mock_grade_repo.get_by_id.return_value = None
    with pytest.raises(InvalidTestReferenceException):
        service.update_test(test_id, TestUpdateRequest(grade_id=uuid.uuid4()), actor_id=uuid.uuid4())


def test_delete_soft_deletes(service, mock_repo):
    test = MagicMock()
    mock_repo.get_by_id.return_value = test
    service.delete_test(test.id, actor_id=uuid.uuid4())
    mock_repo.soft_delete.assert_called_once_with(test)


@pytest.mark.parametrize("duration", [0, -5, 500])
def test_invalid_duration_rejected_by_schema(duration):
    with pytest.raises(ValueError):
        TestCreateRequest(title="Test", duration=duration)


@pytest.mark.parametrize("score", [-1, 101])
def test_invalid_passing_score_rejected_by_schema(score):
    with pytest.raises(ValueError):
        TestCreateRequest(title="Test", passing_score=score)
