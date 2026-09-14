"""Sprint 36 — Student Progress / Lesson Completion tests. Mirrors the
existing MagicMock-based repository mocking pattern used throughout
this project (no real DB)."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.progress.exceptions import LessonNotFoundForProgressException
from app.modules.progress.service import ProgressService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_lesson_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_lesson_repo):
    return ProgressService(mock_repo, mock_lesson_repo)


# --- complete_lesson ---

def test_student_can_complete_a_lesson(service, mock_repo, mock_lesson_repo):
    user_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    mock_lesson_repo.get_by_id.return_value = MagicMock(id=lesson_id)
    mock_repo.get_for_user_and_lesson.return_value = None

    service.complete_lesson(user_id, lesson_id)

    mock_repo.create.assert_called_once()
    mock_repo.db.commit.assert_called_once()


def test_completion_creates_exactly_one_progress_record_with_correct_fields(service, mock_repo, mock_lesson_repo):
    user_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    mock_lesson_repo.get_by_id.return_value = MagicMock(id=lesson_id)
    mock_repo.get_for_user_and_lesson.return_value = None

    service.complete_lesson(user_id, lesson_id)

    created = mock_repo.create.call_args[0][0]
    assert created.user_id == user_id
    assert created.lesson_id == lesson_id
    assert created.completed_at is not None


def test_completing_the_same_lesson_twice_is_idempotent_no_duplicate_created(service, mock_repo, mock_lesson_repo):
    user_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    mock_lesson_repo.get_by_id.return_value = MagicMock(id=lesson_id)
    existing = MagicMock(user_id=user_id, lesson_id=lesson_id)
    mock_repo.get_for_user_and_lesson.return_value = existing

    result = service.complete_lesson(user_id, lesson_id)

    assert result is existing
    mock_repo.create.assert_not_called()


def test_invalid_nonexistent_lesson_is_rejected(service, mock_repo, mock_lesson_repo):
    mock_lesson_repo.get_by_id.return_value = None
    with pytest.raises(LessonNotFoundForProgressException):
        service.complete_lesson(uuid.uuid4(), uuid.uuid4())
    mock_repo.create.assert_not_called()


def test_user_id_always_comes_from_the_caller_not_request_data(service, mock_repo, mock_lesson_repo):
    """The service signature itself enforces this — complete_lesson only
    accepts (user_id, lesson_id) as plain arguments derived from
    get_current_user in the router, never a client-suppliable "on
    behalf of" field. This test documents/locks that contract."""
    import inspect
    sig = inspect.signature(service.complete_lesson)
    assert list(sig.parameters.keys()) == ["user_id", "lesson_id"]


# --- get_my_progress ---

def test_student_can_retrieve_own_progress(service, mock_repo, mock_lesson_repo):
    user_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    mock_repo.list_for_user.return_value = [MagicMock(lesson_id=lesson_id)]
    mock_repo.count_all_lessons.return_value = 4

    result = service.get_my_progress(user_id)

    assert result.completed_lessons == 1
    assert result.total_lessons == 4
    assert result.percentage == 25.0
    assert lesson_id in result.completed_lesson_ids
    mock_repo.list_for_user.assert_called_once_with(user_id)


def test_student_cannot_retrieve_another_students_progress(service, mock_repo, mock_lesson_repo):
    """The repository is always queried with the CALLER's own user_id —
    there is no code path where a different user_id could be substituted."""
    student_a = uuid.uuid4()
    mock_repo.list_for_user.return_value = []
    mock_repo.count_all_lessons.return_value = 10

    service.get_my_progress(student_a)

    mock_repo.list_for_user.assert_called_once_with(student_a)


def test_empty_progress_returns_zero_percentage_not_a_division_error(service, mock_repo):
    mock_repo.list_for_user.return_value = []
    mock_repo.count_all_lessons.return_value = 0  # no lessons exist at all yet

    result = service.get_my_progress(uuid.uuid4())

    assert result.percentage == 0.0
    assert result.completed_lessons == 0
    assert result.total_lessons == 0


def test_percentage_rounds_to_one_decimal(service, mock_repo):
    mock_repo.list_for_user.return_value = [
        MagicMock(lesson_id=uuid.uuid4()), MagicMock(lesson_id=uuid.uuid4()),
    ]  # 2 completed
    mock_repo.count_all_lessons.return_value = 3  # 2/3 = 66.666...

    result = service.get_my_progress(uuid.uuid4())

    assert result.percentage == 66.7
