"""
Business logic for test management. Validates subject_id/grade_id/topic_id
references using existing, unmodified repositories (read-only reuse, same
pattern as topics → subjects/grades). Enforces the publish-readiness rule
and status-transition rules described in
docs/Sprint6_TestEngine_Architecture.md Section 11.
"""
import uuid

from app.core.audit import log_action
from app.modules.grades.repository import GradeRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.tests.exceptions import (
    CannotPublishEmptyTestException,
    InvalidStatusTransitionException,
    InvalidTestReferenceException,
    TestNotFoundException,
)
from app.modules.tests.models import Test, TestStatus
from app.modules.tests.repository import TestRepository
from app.modules.tests.schemas import TestCreateRequest, TestListParams, TestUpdateRequest
from app.modules.tests.validators import is_valid_status_transition
from app.modules.topics.repository import TopicRepository


class TestService:
    def __init__(
        self,
        repository: TestRepository,
        subject_repository: SubjectRepository,
        grade_repository: GradeRepository,
        topic_repository: TopicRepository,
    ):
        self.repo = repository
        self.subject_repo = subject_repository
        self.grade_repo = grade_repository
        self.topic_repo = topic_repository

    def get_test(self, test_id: uuid.UUID) -> Test:
        test = self.repo.get_by_id(test_id)
        if test is None:
            raise TestNotFoundException("Test topilmadi")
        return test

    def list_tests(self, params: TestListParams) -> tuple[list[Test], int]:
        return self.repo.list(params)

    def create_test(self, data: TestCreateRequest, actor_id: uuid.UUID) -> Test:
        self._validate_references(data.subject_id, data.grade_id, data.topic_id)

        test = Test(
            subject_id=data.subject_id,
            grade_id=data.grade_id,
            topic_id=data.topic_id,
            title=data.title,
            description=data.description,
            difficulty=data.difficulty,
            duration=data.duration,
            passing_score=data.passing_score,
            shuffle_questions=data.shuffle_questions,
            shuffle_answers=data.shuffle_answers,
            created_by=actor_id,
        )
        self.repo.create(test)
        log_action(self.repo.db, action="test.created", user_id=actor_id, entity_type="test", entity_id=test.id)
        self.repo.commit()
        return test

    def update_test(self, test_id: uuid.UUID, data: TestUpdateRequest, actor_id: uuid.UUID) -> Test:
        test = self.get_test(test_id)
        updates = data.model_dump(exclude_unset=True)

        self._validate_references(
            updates.get("subject_id", test.subject_id),
            updates.get("grade_id", test.grade_id),
            updates.get("topic_id", test.topic_id),
        )

        updates["updated_by"] = actor_id
        self.repo.update(test, updates)
        log_action(
            self.repo.db, action="test.updated", user_id=actor_id,
            entity_type="test", entity_id=test_id, metadata={"fields": list(updates.keys())},
        )
        self.repo.commit()
        return test

    def publish_test(self, test_id: uuid.UUID, actor_id: uuid.UUID) -> Test:
        test = self.get_test(test_id)
        if not is_valid_status_transition(test.status, TestStatus.PUBLISHED.value):
            raise InvalidStatusTransitionException(f"'{test.status}' holatidan 'published'ga o'tib bo'lmaydi")
        if test.question_count < 1:
            raise CannotPublishEmptyTestException("Kamida bitta savol bo'lmagan testni e'lon qilib bo'lmaydi")

        self.repo.update(test, {"status": TestStatus.PUBLISHED.value, "updated_by": actor_id})
        log_action(self.repo.db, action="test.published", user_id=actor_id, entity_type="test", entity_id=test_id)
        self.repo.commit()
        return test

    def delete_test(self, test_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        test = self.get_test(test_id)
        self.repo.soft_delete(test)
        log_action(self.repo.db, action="test.deleted", user_id=actor_id, entity_type="test", entity_id=test_id)
        self.repo.commit()

    def _validate_references(
        self, subject_id: uuid.UUID | None, grade_id: uuid.UUID | None, topic_id: uuid.UUID | None
    ) -> None:
        if subject_id is not None and self.subject_repo.get_by_id(subject_id) is None:
            raise InvalidTestReferenceException("Ko'rsatilgan fan (subject_id) mavjud emas")
        if grade_id is not None and self.grade_repo.get_by_id(grade_id) is None:
            raise InvalidTestReferenceException("Ko'rsatilgan sinf/daraja (grade_id) mavjud emas")
        if topic_id is not None and self.topic_repo.get_by_id(topic_id) is None:
            raise InvalidTestReferenceException("Ko'rsatilgan mavzu (topic_id) mavjud emas")
