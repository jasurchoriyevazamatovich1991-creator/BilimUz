"""Unit tests for GradeService — repository mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.grades.exceptions import GradeAlreadyExistsException, GradeNotFoundException
from app.modules.grades.schemas import GradeCreateRequest, GradeUpdateRequest
from app.modules.grades.service import GradeService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return GradeService(mock_repo)


def test_create_raises_if_name_taken(service, mock_repo):
    mock_repo.get_by_name.return_value = MagicMock()
    with pytest.raises(GradeAlreadyExistsException):
        service.create_grade(GradeCreateRequest(name="5-sinf"), actor_id=uuid.uuid4())


def test_create_succeeds_for_new_name(service, mock_repo):
    mock_repo.get_by_name.return_value = None
    grade = service.create_grade(GradeCreateRequest(name="6-sinf"), actor_id=uuid.uuid4())
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()
    assert grade.name == "6-sinf"


def test_get_grade_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(GradeNotFoundException):
        service.get_grade(uuid.uuid4())


def test_update_grade_status(service, mock_repo):
    grade_id = uuid.uuid4()
    mock_repo.get_by_id.return_value = MagicMock(id=grade_id)
    service.update_grade(grade_id, GradeUpdateRequest(status="inactive"), actor_id=uuid.uuid4())
    mock_repo.update.assert_called_once()
    called_updates = mock_repo.update.call_args[0][1]
    assert called_updates["status"] == "inactive"


def test_delete_soft_deletes(service, mock_repo):
    grade = MagicMock()
    mock_repo.get_by_id.return_value = grade
    service.delete_grade(grade.id, actor_id=uuid.uuid4())
    mock_repo.soft_delete.assert_called_once_with(grade)
    mock_repo.commit.assert_called_once()


def test_invalid_status_rejected_by_schema():
    with pytest.raises(ValueError):
        GradeUpdateRequest(status="not-a-real-status")


@pytest.mark.parametrize("name", ["", "A", "A" * 101])
def test_invalid_name_length_rejected_by_schema(name):
    with pytest.raises(ValueError):
        GradeCreateRequest(name=name)
