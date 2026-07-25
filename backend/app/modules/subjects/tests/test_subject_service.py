"""Unit tests for SubjectService — repository mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.subjects.exceptions import SubjectAlreadyExistsException, SubjectNotFoundException
from app.modules.subjects.schemas import SubjectCreateRequest, SubjectUpdateRequest
from app.modules.subjects.service import SubjectService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return SubjectService(mock_repo)


def test_create_raises_if_name_taken(service, mock_repo):
    mock_repo.get_by_name.return_value = MagicMock()
    with pytest.raises(SubjectAlreadyExistsException):
        service.create_subject(SubjectCreateRequest(name="Matematika"), actor_id=uuid.uuid4())


def test_create_succeeds_for_new_name(service, mock_repo):
    mock_repo.get_by_name.return_value = None
    subject = service.create_subject(SubjectCreateRequest(name="Fizika"), actor_id=uuid.uuid4())
    mock_repo.create.assert_called_once()
    mock_repo.commit.assert_called_once()
    assert subject.name == "Fizika"


def test_get_subject_raises_when_missing(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(SubjectNotFoundException):
        service.get_subject(uuid.uuid4())


def test_update_rejects_duplicate_name(service, mock_repo):
    existing = MagicMock()
    existing.name = "Kimyo"  # NOTE: MagicMock(name=...) does NOT set this — name is a reserved
    mock_repo.get_by_id.return_value = existing        # kwarg for the mock's own repr (see BUG-003)
    mock_repo.get_by_name.return_value = MagicMock()  # another subject already has this name
    with pytest.raises(SubjectAlreadyExistsException):
        service.update_subject(uuid.uuid4(), SubjectUpdateRequest(name="Biologiya"), actor_id=uuid.uuid4())


def test_delete_soft_deletes(service, mock_repo):
    subject = MagicMock()
    mock_repo.get_by_id.return_value = subject
    actor = uuid.uuid4()
    service.delete_subject(subject.id, actor_id=actor)
    mock_repo.soft_delete.assert_called_once_with(subject, deleted_by=actor)


def test_invalid_sort_field_falls_back_to_default(service, mock_repo):
    mock_repo.list.return_value = ([], 0)
    from app.modules.subjects.schemas import SubjectListParams
    params = SubjectListParams(sort="'; DROP TABLE subjects;--")
    service.list_subjects(params)
    called_params = mock_repo.list.call_args[0][0]
    assert called_params.sort == "-created_at"


def test_update_allows_case_only_rename(service, mock_repo):
    """Regression test for BUG-001: renaming 'Matematika' -> 'MATEMATIKA'
    must NOT collide with itself. get_by_name must receive exclude_id."""
    subject = MagicMock(id=uuid.uuid4(), name="Matematika")
    mock_repo.get_by_id.return_value = subject
    mock_repo.get_by_name.return_value = None  # correctly excludes self now

    service.update_subject(subject.id, SubjectUpdateRequest(name="MATEMATIKA"), actor_id=uuid.uuid4())

    mock_repo.get_by_name.assert_called_once_with("MATEMATIKA", exclude_id=subject.id)
    mock_repo.update.assert_called_once()
