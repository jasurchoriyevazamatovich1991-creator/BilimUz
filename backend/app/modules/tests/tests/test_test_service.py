"""Unit tests for TestService — all repositories mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.tests.exceptions import (
    CannotPublishEmptyTestException,
    InvalidStatusTransitionException,
    InvalidTestReferenceException,
    MockTestRequiresSubjectException,
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
    data = TestCreateRequest(subject_id=uuid.uuid4(), title="Matematika DTM", duration=60)
    with pytest.raises(InvalidTestReferenceException):
        service.create_test(data, actor_id=uuid.uuid4())


def test_create_succeeds_with_no_references(service, mock_repo):
    """subject_id/grade_id/topic_id are all optional — a test can exist
    without being scoped to any of them."""
    data = TestCreateRequest(title="Umumiy test", duration=60)
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
        TestCreateRequest(title="Test", duration=60, passing_score=score)


def test_duration_is_now_required_by_schema():
    """Mock Test Entitlements spec §3 — 'the teacher/admin must specify
    its duration before publishing it.' Omitting duration entirely must
    fail, not silently fall back to 60 anymore."""
    with pytest.raises(ValueError):
        TestCreateRequest(title="Test")


# --- is_mock_test / subject-direction consistency (Mock Test Entitlements) ---

def test_schema_rejects_mock_test_without_subject():
    with pytest.raises(ValueError):
        TestCreateRequest(title="Fizika mock", duration=60, is_mock_test=True)


def test_schema_accepts_mock_test_with_subject():
    req = TestCreateRequest(title="Fizika mock", duration=60, is_mock_test=True, subject_id=uuid.uuid4())
    assert req.is_mock_test is True


def test_schema_accepts_non_mock_test_without_subject():
    req = TestCreateRequest(title="Oddiy test", duration=60, is_mock_test=False)
    assert req.subject_id is None


def test_create_mock_test_requires_subject_at_service_layer_too(service, mock_subject_repo):
    """Defense in depth — even if a caller built TestCreateRequest
    without going through Pydantic's own validation, the service layer
    independently refuses the same inconsistent state."""
    mock_subject_repo.get_by_id.return_value = MagicMock()
    data = TestCreateRequest.model_construct(
        subject_id=None, grade_id=None, topic_id=None, title="Test", description=None,
        difficulty="medium", duration=60, passing_score=None, shuffle_questions=True,
        shuffle_answers=True, max_attempts=None, exam_variant=None, is_mock_test=True,
    )
    with pytest.raises(MockTestRequiresSubjectException):
        service.create_test(data, actor_id=uuid.uuid4())


def test_create_mock_test_succeeds_with_subject(service, mock_subject_repo, mock_repo):
    mock_subject_repo.get_by_id.return_value = MagicMock()
    subject_id = uuid.uuid4()
    data = TestCreateRequest(title="IELTS mock", duration=120, is_mock_test=True, subject_id=subject_id)
    test = service.create_test(data, actor_id=uuid.uuid4())
    assert test.is_mock_test is True
    assert test.subject_id == subject_id


def test_update_rejects_turning_on_mock_test_without_existing_or_new_subject(service, mock_repo):
    """Partial-update case: the existing row has no subject_id, and the
    PATCH only sets is_mock_test=True without also supplying subject_id
    — must be rejected using the MERGED state, not just the submitted
    fields."""
    test_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=test_id, subject_id=None, grade_id=None, topic_id=None, is_mock_test=False)
    with pytest.raises(MockTestRequiresSubjectException):
        service.update_test(test_id, TestUpdateRequest(is_mock_test=True), actor_id=uuid.uuid4())


def test_update_allows_turning_on_mock_test_when_subject_already_set(service, mock_repo):
    test_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=test_id, subject_id=subject_id, grade_id=None, topic_id=None, is_mock_test=False)
    service.update_test(test_id, TestUpdateRequest(is_mock_test=True), actor_id=uuid.uuid4())
    called_updates = mock_repo.update.call_args[0][1]
    assert called_updates["is_mock_test"] is True


def test_update_rejects_clearing_subject_on_an_existing_mock_test(service, mock_repo):
    """The other direction: an already-mock test's subject_id cannot be
    cleared while it remains flagged as a mock test."""
    test_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=test_id, subject_id=uuid.uuid4(), grade_id=None, topic_id=None, is_mock_test=True)
    with pytest.raises(MockTestRequiresSubjectException):
        service.update_test(test_id, TestUpdateRequest(subject_id=None), actor_id=uuid.uuid4())
