"""
Business logic for questions/options/media. Reads and writes to
TestRepository.increment_question_count() (existing, unmodified method,
added in the tests module specifically for this reuse) so
tests.question_count never drifts. Validates test_id references using
the existing, unmodified TestRepository (read-only pattern, same as
topics → subjects/grades).
"""
import uuid

from app.core.audit import log_action
from app.modules.questions.exceptions import (
    InvalidOptionConfigurationException,
    InvalidTestReferenceException,
    MediaNotFoundException,
    OptionNotFoundException,
    QuestionNotFoundException,
    UploadNotFoundForMediaException,
)
from app.modules.questions.models import Question, QuestionMedia, QuestionOption
from app.modules.questions.repository import MediaRepository, OptionRepository, QuestionRepository
from app.modules.questions.schemas import (
    MediaCreateRequest,
    OptionCreateRequest,
    OptionUpdateRequest,
    QuestionCreateRequest,
    QuestionListParams,
    QuestionUpdateRequest,
)
from app.modules.tests.repository import TestRepository
from app.modules.uploads.repository import UploadRepository


class QuestionService:
    def __init__(self, repository: QuestionRepository, test_repository: TestRepository):
        self.repo = repository
        self.test_repo = test_repository

    def get_question(self, question_id: uuid.UUID) -> Question:
        question = self.repo.get_by_id(question_id)
        if question is None:
            raise QuestionNotFoundException("Savol topilmadi")
        return question

    def list_questions(self, params: QuestionListParams) -> tuple[list[Question], int]:
        return self.repo.list(params)

    def create_question(self, data: QuestionCreateRequest, actor_id: uuid.UUID) -> Question:
        if self.test_repo.get_by_id(data.test_id) is None:
            raise InvalidTestReferenceException("Ko'rsatilgan test (test_id) mavjud emas")

        question = Question(
            test_id=data.test_id,
            question_text=data.question_text,
            question_type=data.question_type,
            difficulty=data.difficulty,
            score=data.score,
            explanation=data.explanation,
            created_by=actor_id,
        )
        for opt_data in data.options:
            question.options.append(
                QuestionOption(option_text=opt_data.option_text, is_correct=opt_data.is_correct, created_by=actor_id)
            )

        self.repo.create(question)
        self.test_repo.increment_question_count(data.test_id, delta=1)
        log_action(self.repo.db, action="question.created", user_id=actor_id, entity_type="question", entity_id=question.id)
        self.repo.commit()
        return question

    def update_question(self, question_id: uuid.UUID, data: QuestionUpdateRequest, actor_id: uuid.UUID) -> Question:
        question = self.get_question(question_id)
        updates = data.model_dump(exclude_unset=True)
        updates["updated_by"] = actor_id
        self.repo.update(question, updates)
        log_action(
            self.repo.db, action="question.updated", user_id=actor_id,
            entity_type="question", entity_id=question_id, metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return question

    def delete_question(self, question_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        question = self.get_question(question_id)
        self.repo.soft_delete(question)
        self.test_repo.increment_question_count(question.test_id, delta=-1)
        log_action(self.repo.db, action="question.deleted", user_id=actor_id, entity_type="question", entity_id=question_id)
        self.repo.commit()


class OptionService:
    def __init__(self, repository: OptionRepository, question_repository: QuestionRepository):
        self.repo = repository
        self.question_repo = question_repository

    def add_option(self, question_id: uuid.UUID, data: OptionCreateRequest, actor_id: uuid.UUID) -> QuestionOption:
        question = self.question_repo.get_by_id(question_id)
        if question is None:
            raise QuestionNotFoundException("Savol topilmadi")

        # Full option-set completeness (minimum count, "at least one correct"
        # for multiple_choice) can only be judged once the set is complete —
        # enforced at question-creation time (QuestionCreateRequest) and
        # should additionally be checked at test-publish time (see
        # docs/Sprint6_TestEngine_Architecture.md — flagged as a Sprint 6
        # follow-up, not implemented here to avoid a questions→tests
        # dependency that would violate the one-directional module rule).
        #
        # What CAN always be enforced, regardless of how many options exist
        # yet, is this: a single_choice/true_false question can never have
        # two options marked correct at the same time.
        if question.question_type in ("single_choice", "true_false") and data.is_correct:
            existing = self.repo.list_for_question(question_id)
            if any(o.is_correct for o in existing):
                raise InvalidOptionConfigurationException(
                    f"'{question.question_type}' turida faqat 1 ta to'g'ri variant bo'lishi mumkin"
                )

        option = QuestionOption(question_id=question_id, option_text=data.option_text, is_correct=data.is_correct, created_by=actor_id)
        self.repo.create(option)
        self.repo.db.commit()
        return option

    def update_option(self, option_id: uuid.UUID, data: OptionUpdateRequest, actor_id: uuid.UUID) -> QuestionOption:
        option = self._require_option(option_id)
        updates = data.model_dump(exclude_unset=True)

        if updates.get("is_correct") is True:
            question = self.question_repo.get_by_id(option.question_id)
            if question is not None and question.question_type in ("single_choice", "true_false"):
                siblings = self.repo.list_for_question(option.question_id)
                if any(o.is_correct and o.id != option_id for o in siblings):
                    raise InvalidOptionConfigurationException(
                        f"'{question.question_type}' turida faqat 1 ta to'g'ri variant bo'lishi mumkin"
                    )

        updates["updated_by"] = actor_id
        self.repo.update(option, updates)
        self.repo.db.commit()
        return option

    def delete_option(self, option_id: uuid.UUID) -> None:
        option = self._require_option(option_id)
        self.repo.soft_delete(option)
        self.repo.db.commit()

    def _require_option(self, option_id: uuid.UUID) -> QuestionOption:
        option = self.repo.get_by_id(option_id)
        if option is None:
            raise OptionNotFoundException("Variant topilmadi")
        return option


class MediaService:
    def __init__(
        self,
        repository: MediaRepository,
        question_repository: QuestionRepository,
        option_repository: OptionRepository,
        upload_repository: UploadRepository,
    ):
        self.repo = repository
        self.question_repo = question_repository
        self.option_repo = option_repository
        self.upload_repo = upload_repository

    def add_media(self, question_id: uuid.UUID, data: MediaCreateRequest, actor_id: uuid.UUID) -> QuestionMedia:
        if self.question_repo.get_by_id(question_id) is None:
            raise QuestionNotFoundException("Savol topilmadi")

        if data.option_id is not None:
            option = self.option_repo.get_by_id(data.option_id)
            if option is None or option.question_id != question_id:
                raise OptionNotFoundException("Ko'rsatilgan variant (option_id) bu savolga tegishli emas")

        file_url = data.file_url
        upload_id = data.upload_id
        if data.upload_id is not None:
            # Sprint 32 — the real, R2-backed path. `Upload.file_url`
            # for an R2-backed row is the OBJECT KEY, not a directly
            # browsable URL (matches Sprint 27's private-bucket design
            # exactly) — the frontend must call GET /uploads/{id}/
            # view-url for a real, short-lived signed URL rather than
            # treating this stored value as browsable. Stored here only
            # to satisfy the existing NOT NULL file_url column and for
            # backward-compatible display of legacy (non-R2) rows.
            upload = self.upload_repo.get_by_id(data.upload_id)
            if upload is None:
                raise UploadNotFoundForMediaException("Ko'rsatilgan fayl (upload_id) topilmadi")
            file_url = upload.file_url

        media = QuestionMedia(
            question_id=question_id, option_id=data.option_id, media_type=data.media_type,
            file_url=file_url, upload_id=upload_id, created_by=actor_id,
        )
        self.repo.create(media)
        self.repo.db.commit()
        return media

    def delete_media(self, media_id: uuid.UUID) -> None:
        media = self.repo.get_by_id(media_id)
        if media is None:
            raise MediaNotFoundException("Media fayl topilmadi")
        self.repo.soft_delete(media)
        self.repo.db.commit()
