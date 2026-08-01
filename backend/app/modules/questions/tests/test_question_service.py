"""Unit tests for QuestionService, OptionService, MediaService — all
repositories mocked, no real DB needed."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.modules.questions.exceptions import (
    InvalidOptionConfigurationException,
    InvalidTestReferenceException,
    MediaNotFoundException,
    OptionNotFoundException,
    QuestionNotFoundException,
)
from app.modules.questions.schemas import (
    MediaCreateRequest,
    OptionCreateRequest,
    QuestionCreateRequest,
    QuestionUpdateRequest,
)
from app.modules.questions.service import MediaService, OptionService, QuestionService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_test_repo():
    return MagicMock()


@pytest.fixture
def question_service(mock_repo, mock_test_repo):
    return QuestionService(mock_repo, mock_test_repo)


def test_create_rejects_invalid_test(question_service, mock_test_repo):
    mock_test_repo.get_by_id.return_value = None
    data = QuestionCreateRequest(
        test_id=uuid.uuid4(), question_text="2+2 nechiga teng?",
        options=[OptionCreateRequest(option_text="4", is_correct=True), OptionCreateRequest(option_text="5")],
    )
    with pytest.raises(InvalidTestReferenceException):
        question_service.create_question(data, actor_id=uuid.uuid4())


def test_create_succeeds_and_increments_test_count(question_service, mock_repo, mock_test_repo):
    mock_test_repo.get_by_id.return_value = MagicMock()
    test_id = uuid.uuid4()
    data = QuestionCreateRequest(
        test_id=test_id, question_text="2+2 nechiga teng?",
        options=[OptionCreateRequest(option_text="4", is_correct=True), OptionCreateRequest(option_text="5")],
    )
    question = question_service.create_question(data, actor_id=uuid.uuid4())
    mock_test_repo.increment_question_count.assert_called_once_with(test_id, delta=1)
    assert len(question.options) == 2


def test_schema_rejects_single_choice_with_two_correct_answers():
    with pytest.raises(ValueError):
        QuestionCreateRequest(
            test_id=uuid.uuid4(), question_text="Savol matni",
            question_type="single_choice",
            options=[
                OptionCreateRequest(option_text="A", is_correct=True),
                OptionCreateRequest(option_text="B", is_correct=True),
            ],
        )


def test_schema_rejects_choice_question_with_one_option():
    with pytest.raises(ValueError):
        QuestionCreateRequest(
            test_id=uuid.uuid4(), question_text="Savol matni",
            question_type="single_choice",
            options=[OptionCreateRequest(option_text="Yagona variant", is_correct=True)],
        )


def test_schema_allows_essay_with_no_options():
    q = QuestionCreateRequest(test_id=uuid.uuid4(), question_text="Insho yozing", question_type="essay")
    assert q.options == []


def test_get_question_raises_when_missing(question_service, mock_repo):
    mock_repo.get_by_id.return_value = None
    with pytest.raises(QuestionNotFoundException):
        question_service.get_question(uuid.uuid4())


def test_delete_decrements_test_count(question_service, mock_repo, mock_test_repo):
    question = MagicMock(test_id=uuid.uuid4())
    mock_repo.get_by_id.return_value = question
    question_service.delete_question(question.id, actor_id=uuid.uuid4())
    mock_test_repo.increment_question_count.assert_called_once_with(question.test_id, delta=-1)


# --- OptionService ---------------------------------------------------------

@pytest.fixture
def mock_option_repo():
    return MagicMock()


@pytest.fixture
def mock_question_repo():
    return MagicMock()


@pytest.fixture
def option_service(mock_option_repo, mock_question_repo):
    return OptionService(mock_option_repo, mock_question_repo)


def test_add_option_rejects_second_correct_for_single_choice(option_service, mock_option_repo, mock_question_repo):
    question_id = uuid.uuid4()
    mock_question_repo.get_by_id.return_value = MagicMock(question_type="single_choice")
    mock_option_repo.list_for_question.return_value = [MagicMock(is_correct=True)]
    with pytest.raises(InvalidOptionConfigurationException):
        option_service.add_option(question_id, OptionCreateRequest(option_text="Yana bir to'g'ri", is_correct=True), actor_id=uuid.uuid4())


def test_add_option_allows_second_incorrect_for_single_choice(option_service, mock_option_repo, mock_question_repo):
    question_id = uuid.uuid4()
    mock_question_repo.get_by_id.return_value = MagicMock(question_type="single_choice")
    mock_option_repo.list_for_question.return_value = [MagicMock(is_correct=True)]
    option = option_service.add_option(question_id, OptionCreateRequest(option_text="Noto'g'ri variant", is_correct=False), actor_id=uuid.uuid4())
    mock_option_repo.create.assert_called_once()


def test_add_option_raises_when_question_missing(option_service, mock_question_repo):
    mock_question_repo.get_by_id.return_value = None
    with pytest.raises(QuestionNotFoundException):
        option_service.add_option(uuid.uuid4(), OptionCreateRequest(option_text="X"), actor_id=uuid.uuid4())


def test_delete_option_raises_when_missing(option_service, mock_option_repo):
    mock_option_repo.get_by_id.return_value = None
    with pytest.raises(OptionNotFoundException):
        option_service.delete_option(uuid.uuid4())


# --- MediaService ------------------------------------------------------------

@pytest.fixture
def mock_media_repo():
    return MagicMock()


@pytest.fixture
def media_service(mock_media_repo, mock_question_repo):
    return MediaService(mock_media_repo, mock_question_repo)


def test_add_media_rejects_invalid_question(media_service, mock_question_repo):
    mock_question_repo.get_by_id.return_value = None
    with pytest.raises(QuestionNotFoundException):
        media_service.add_media(uuid.uuid4(), MediaCreateRequest(media_type="image", file_url="https://example.com/x.png"), actor_id=uuid.uuid4())


def test_add_media_succeeds(media_service, mock_media_repo, mock_question_repo):
    mock_question_repo.get_by_id.return_value = MagicMock()
    media = media_service.add_media(uuid.uuid4(), MediaCreateRequest(media_type="image", file_url="https://example.com/x.png"), actor_id=uuid.uuid4())
    mock_media_repo.create.assert_called_once()


def test_delete_media_raises_when_missing(media_service, mock_media_repo):
    mock_media_repo.get_by_id.return_value = None
    with pytest.raises(MediaNotFoundException):
        media_service.delete_media(uuid.uuid4())


def test_schema_rejects_invalid_media_type():
    with pytest.raises(ValueError):
        MediaCreateRequest(media_type="not-a-type", file_url="https://example.com/x.png")
