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
    DuplicateOrderNumberException,
    ExamModuleNotFoundException,
    ExamSectionNotFoundException,
    InvalidStatusTransitionException,
    InvalidTestReferenceException,
    TestNotFoundException,
)
from app.modules.tests.models import ExamModule, ExamSection, Test, TestStatus
from app.modules.tests.repository import ExamModuleRepository, ExamSectionRepository, TestRepository
from app.modules.tests.schemas import (
    ExamModuleCreateRequest,
    ExamModuleUpdateRequest,
    ExamSectionCreateRequest,
    ExamSectionUpdateRequest,
    TestCreateRequest,
    TestListParams,
    TestUpdateRequest,
)
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
            max_attempts=data.max_attempts,
            exam_variant=data.exam_variant,
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


class ExamSectionService:
    """Sprint 51 — Admin Configuration API for ExamSection (Sprint 45).
    Mirrors TestService's own validation style (existence checks via
    the already-existing repositories, clean domain exceptions instead
    of raw IntegrityError)."""

    def __init__(self, repo: ExamSectionRepository, test_repo: TestRepository):
        self.repo = repo
        self.test_repo = test_repo

    def _ensure_no_duplicate_order(self, test_id: uuid.UUID, order_number: int, exclude_id: uuid.UUID | None = None) -> None:
        for existing in self.repo.list_for_test(test_id):
            if existing.order_number == order_number and existing.id != exclude_id:
                raise DuplicateOrderNumberException(f"Bu test uchun order_number={order_number} allaqachon band")

    def create_section(self, data: ExamSectionCreateRequest, actor_id: uuid.UUID) -> ExamSection:
        if self.test_repo.get_by_id(data.test_id) is None:
            raise InvalidTestReferenceException("Ko'rsatilgan test (test_id) mavjud emas")
        self._ensure_no_duplicate_order(data.test_id, data.order_number)

        section = ExamSection(test_id=data.test_id, name=data.name, order_number=data.order_number, duration=data.duration)
        self.repo.create(section)
        log_action(self.repo.db, action="exam_section.created", user_id=actor_id, entity_type="exam_section", entity_id=section.id)
        self.repo.commit()
        return section

    def list_sections(self, test_id: uuid.UUID) -> list[ExamSection]:
        if self.test_repo.get_by_id(test_id) is None:
            raise InvalidTestReferenceException("Ko'rsatilgan test (test_id) mavjud emas")
        return self.repo.list_for_test(test_id)

    def get_section(self, section_id: uuid.UUID) -> ExamSection:
        section = self.repo.get_by_id(section_id)
        if section is None or section.deleted_at is not None:
            raise ExamSectionNotFoundException("Bo'lim topilmadi")
        return section

    def update_section(self, section_id: uuid.UUID, data: ExamSectionUpdateRequest, actor_id: uuid.UUID) -> ExamSection:
        section = self.get_section(section_id)
        payload = data.model_dump(exclude_unset=True)
        if "order_number" in payload:
            self._ensure_no_duplicate_order(section.test_id, payload["order_number"], exclude_id=section.id)
        self.repo.update(section, payload)
        log_action(self.repo.db, action="exam_section.updated", user_id=actor_id, entity_type="exam_section", entity_id=section.id)
        self.repo.commit()
        return section


class ExamModuleService:
    """Sprint 51 — Admin Configuration API for ExamModule (Sprint 46).
    Mirrors ExamSectionService's own shape exactly — same validation
    style, same duplicate-order-number guard at (section, order_number)
    scope instead of (test, order_number)."""

    def __init__(self, repo: ExamModuleRepository, section_repo: ExamSectionRepository):
        self.repo = repo
        self.section_repo = section_repo

    def _ensure_no_duplicate_order(self, section_id: uuid.UUID, order_number: int, exclude_id: uuid.UUID | None = None) -> None:
        for existing in self.repo.list_for_section(section_id):
            if existing.order_number == order_number and existing.id != exclude_id:
                raise DuplicateOrderNumberException(f"Bu bo'lim uchun order_number={order_number} allaqachon band")

    def create_module(self, data: ExamModuleCreateRequest, actor_id: uuid.UUID) -> ExamModule:
        if self.section_repo.get_by_id(data.section_id) is None:
            raise ExamSectionNotFoundException("Ko'rsatilgan bo'lim (section_id) mavjud emas")
        self._ensure_no_duplicate_order(data.section_id, data.order_number)

        module = ExamModule(
            section_id=data.section_id, name=data.name, order_number=data.order_number, duration=data.duration,
            difficulty_tier=data.difficulty_tier, routing_group=data.routing_group, routing_variant=data.routing_variant,
        )
        self.repo.create(module)
        log_action(self.repo.db, action="exam_module.created", user_id=actor_id, entity_type="exam_module", entity_id=module.id)
        self.repo.commit()
        return module

    def list_modules(self, section_id: uuid.UUID) -> list[ExamModule]:
        if self.section_repo.get_by_id(section_id) is None:
            raise ExamSectionNotFoundException("Ko'rsatilgan bo'lim (section_id) mavjud emas")
        return self.repo.list_for_section(section_id)

    def get_module(self, module_id: uuid.UUID) -> ExamModule:
        module = self.repo.get_by_id(module_id)
        if module is None or module.deleted_at is not None:
            raise ExamModuleNotFoundException("Modul topilmadi")
        return module

    def update_module(self, module_id: uuid.UUID, data: ExamModuleUpdateRequest, actor_id: uuid.UUID) -> ExamModule:
        module = self.get_module(module_id)
        payload = data.model_dump(exclude_unset=True)
        if "order_number" in payload:
            self._ensure_no_duplicate_order(module.section_id, payload["order_number"], exclude_id=module.id)
        self.repo.update(module, payload)
        log_action(self.repo.db, action="exam_module.updated", user_id=actor_id, entity_type="exam_module", entity_id=module.id)
        self.repo.commit()
        return module
