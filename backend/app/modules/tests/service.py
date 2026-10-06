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
    DuplicateRoutingThresholdRuleException,
    ExamModuleNotFoundException,
    ExamSectionNotFoundException,
    InvalidStatusTransitionException,
    InvalidTestReferenceException,
    QuestionGroupNotFoundException,
    RoutingThresholdRuleNotFoundException,
    TestNotFoundException,
)
from app.modules.tests.models import ExamModule, ExamSection, QuestionGroup, RoutingThresholdRule, Test, TestStatus
from app.modules.tests.repository import (
    ExamModuleRepository,
    ExamSectionRepository,
    QuestionGroupRepository,
    RoutingThresholdRuleRepository,
    TestRepository,
)
from app.modules.tests.schemas import (
    ExamModuleCreateRequest,
    ExamModuleUpdateRequest,
    ExamSectionCreateRequest,
    ExamSectionUpdateRequest,
    QuestionGroupCreateRequest,
    QuestionGroupUpdateRequest,
    RoutingThresholdRuleCreateRequest,
    RoutingThresholdRuleUpdateRequest,
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

    def __init__(self, repo: ExamModuleRepository, section_repo: ExamSectionRepository, test_repo: TestRepository):
        self.repo = repo
        self.section_repo = section_repo
        self.test_repo = test_repo

    def _ensure_no_duplicate_order(self, section_id: uuid.UUID, order_number: int, exclude_id: uuid.UUID | None = None) -> None:
        for existing in self.repo.list_for_section(section_id):
            if existing.order_number == order_number and existing.id != exclude_id:
                raise DuplicateOrderNumberException(f"Bu bo'lim uchun order_number={order_number} allaqachon band")

    def create_module(self, data: ExamModuleCreateRequest, actor_id: uuid.UUID) -> ExamModule:
        # Sprint 64 — C1. get_active_by_id() (not get_by_id()) so a
        # soft-deleted ExamSection is rejected exactly like a
        # nonexistent one, closing the gap where a new active module
        # could be attached to a logically-deleted section.
        if self.section_repo.get_active_by_id(data.section_id) is None:
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

    def list_modules_for_test(self, test_id: uuid.UUID) -> list[ExamModule]:
        """Sprint 74 — additive. The Admin Exam Configuration UI needs
        every module across a whole test (to render the full
        Test -> Sections -> Modules tree) without issuing one HTTP
        request per section (an N+1 pattern at the API layer). Reuses
        ExamModuleRepository.list_for_test() exactly as-is — that single
        JOIN query already existed (used internally by
        has_modules()/the attempt-execution path since Sprint 46) and is
        already ordered by (section.order_number, module.order_number).
        No new query logic, no migration."""
        if self.test_repo.get_by_id(test_id) is None:
            raise InvalidTestReferenceException("Ko'rsatilgan test (test_id) mavjud emas")
        return self.repo.list_for_test(test_id)

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


class QuestionGroupService:
    """Sprint 53 — Admin Configuration API for QuestionGroup (Sprint 47).
    Mirrors ExamSectionService's own shape exactly — same duplicate-order
    guard style, same module-ownership validation logic Sprint 52 already
    established for Question assignment (module must exist, must belong
    to a section, that section must belong to the target test)."""

    def __init__(self, repo: QuestionGroupRepository, test_repo: TestRepository, module_repo: ExamModuleRepository, section_repo: ExamSectionRepository):
        self.repo = repo
        self.test_repo = test_repo
        self.module_repo = module_repo
        self.section_repo = section_repo

    def _ensure_no_duplicate_order(self, test_id: uuid.UUID, order_number: int, exclude_id: uuid.UUID | None = None) -> None:
        for existing in self.repo.list_for_test(test_id):
            if existing.order_number == order_number and existing.id != exclude_id:
                raise DuplicateOrderNumberException(f"Bu test uchun order_number={order_number} allaqachon band")

    def _validate_module_belongs_to_test(self, module_id: uuid.UUID, test_id: uuid.UUID) -> None:
        # Sprint 64 — C1. get_active_by_id() on both the module and its
        # section — a soft-deleted ExamModule or a soft-deleted parent
        # ExamSection must both be rejected exactly like a nonexistent
        # one, closing the gap where a new QuestionGroup could be
        # attached to a logically-deleted module/section.
        module = self.module_repo.get_active_by_id(module_id)
        if module is None:
            raise ExamModuleNotFoundException("Ko'rsatilgan modul (module_id) mavjud emas")
        section = self.section_repo.get_active_by_id(module.section_id)
        if section is None or section.test_id != test_id:
            raise InvalidTestReferenceException("Ko'rsatilgan modul (module_id) bu guruhning testiga tegishli emas")

    def create_group(self, data: QuestionGroupCreateRequest, actor_id: uuid.UUID) -> QuestionGroup:
        if self.test_repo.get_by_id(data.test_id) is None:
            raise InvalidTestReferenceException("Ko'rsatilgan test (test_id) mavjud emas")
        if data.module_id is not None:
            self._validate_module_belongs_to_test(data.module_id, data.test_id)
        self._ensure_no_duplicate_order(data.test_id, data.order_number)

        group = QuestionGroup(
            test_id=data.test_id, module_id=data.module_id, title=data.title,
            stimulus_text=data.stimulus_text, order_number=data.order_number,
        )
        self.repo.create(group)
        log_action(self.repo.db, action="question_group.created", user_id=actor_id, entity_type="question_group", entity_id=group.id)
        self.repo.commit()
        return group

    def list_groups(self, test_id: uuid.UUID) -> list[QuestionGroup]:
        if self.test_repo.get_by_id(test_id) is None:
            raise InvalidTestReferenceException("Ko'rsatilgan test (test_id) mavjud emas")
        return self.repo.list_for_test(test_id)

    def get_group(self, group_id: uuid.UUID) -> QuestionGroup:
        group = self.repo.get_by_id(group_id)
        if group is None or group.deleted_at is not None:
            raise QuestionGroupNotFoundException("Guruh topilmadi")
        return group

    def update_group(self, group_id: uuid.UUID, data: QuestionGroupUpdateRequest, actor_id: uuid.UUID) -> QuestionGroup:
        group = self.get_group(group_id)
        payload = data.model_dump(exclude_unset=True)
        # test_id is never in QuestionGroupUpdateRequest at all — a
        # group can never be moved to another test through PATCH.
        if "module_id" in payload and payload["module_id"] is not None:
            self._validate_module_belongs_to_test(payload["module_id"], group.test_id)
        if "order_number" in payload:
            self._ensure_no_duplicate_order(group.test_id, payload["order_number"], exclude_id=group.id)
        self.repo.update(group, payload)
        log_action(self.repo.db, action="question_group.updated", user_id=actor_id, entity_type="question_group", entity_id=group.id)
        self.repo.commit()
        return group

    def delete_group(self, group_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        """Soft delete — matches ExamSection/ExamModule's own
        convention. Question.group_id's ON DELETE SET NULL FK means a
        future hard-delete would be safe too, but this sprint follows
        the established soft-delete pattern rather than introducing a
        second deletion semantics."""
        group = self.get_group(group_id)
        self.repo.soft_delete(group)
        log_action(self.repo.db, action="question_group.deleted", user_id=actor_id, entity_type="question_group", entity_id=group.id)
        self.repo.commit()


class RoutingThresholdRuleService:
    """Sprint 75 completion — Admin Configuration API for
    RoutingThresholdRule (Sprint 75's own persisted threshold config).
    Mirrors QuestionGroupService's own shape exactly: existence/
    ownership checks via already-existing repositories, a service-level
    duplicate guard mirroring the DB's own UNIQUE(test_id, routing_group,
    min_ratio) constraint (so a collision surfaces as a clean 409
    instead of a raw IntegrityError, the same reasoning
    DuplicateOrderNumberException already established), and soft-delete
    instead of a hard DELETE.

    This service introduces NO new routing logic — ModuleExecutionService.
    _select_routing_strategy() already reads RoutingThresholdRuleRepository.
    list_for_test() exactly as this service writes to it. Creating this
    API is the only change: it lets a real admin populate the table that
    was previously reachable only by a test writing rows directly."""

    def __init__(self, repo: RoutingThresholdRuleRepository, test_repo: TestRepository):
        self.repo = repo
        self.test_repo = test_repo

    def _ensure_no_duplicate(
        self, test_id: uuid.UUID, routing_group: str, min_ratio: float, exclude_id: uuid.UUID | None = None
    ) -> None:
        for existing in self.repo.list_for_test(test_id):
            if existing.routing_group == routing_group and float(existing.min_ratio) == float(min_ratio) and existing.id != exclude_id:
                raise DuplicateRoutingThresholdRuleException(
                    f"Bu test uchun routing_group='{routing_group}', min_ratio={min_ratio} qoidasi allaqachon mavjud"
                )

    def create_rule(self, data: RoutingThresholdRuleCreateRequest, actor_id: uuid.UUID) -> RoutingThresholdRule:
        # test must exist and not be soft-deleted — TestRepository.get_by_id
        # already filters deleted_at IS NULL, same existence check every
        # other Admin Configuration endpoint in this module uses (no new
        # "active" status rule invented beyond the established pattern).
        if self.test_repo.get_by_id(data.test_id) is None:
            raise InvalidTestReferenceException("Ko'rsatilgan test (test_id) mavjud emas")
        self._ensure_no_duplicate(data.test_id, data.routing_group, data.min_ratio)

        rule = RoutingThresholdRule(
            test_id=data.test_id, routing_group=data.routing_group, min_ratio=data.min_ratio, variant=data.variant,
        )
        self.repo.create(rule)
        log_action(self.repo.db, action="routing_threshold_rule.created", user_id=actor_id, entity_type="routing_threshold_rule", entity_id=rule.id)
        self.repo.commit()
        return rule

    def list_rules(self, test_id: uuid.UUID) -> list[RoutingThresholdRule]:
        if self.test_repo.get_by_id(test_id) is None:
            raise InvalidTestReferenceException("Ko'rsatilgan test (test_id) mavjud emas")
        return self.repo.list_for_test(test_id)

    def get_rule(self, rule_id: uuid.UUID) -> RoutingThresholdRule:
        rule = self.repo.get_active_by_id(rule_id)
        if rule is None:
            raise RoutingThresholdRuleNotFoundException("Yo'naltirish qoidasi topilmadi")
        return rule

    def update_rule(self, rule_id: uuid.UUID, data: RoutingThresholdRuleUpdateRequest, actor_id: uuid.UUID) -> RoutingThresholdRule:
        rule = self.get_rule(rule_id)
        payload = data.model_dump(exclude_unset=True)
        # test_id is never in RoutingThresholdRuleUpdateRequest at all —
        # a rule can never be moved to another test through PATCH,
        # mirroring QuestionGroupUpdateRequest's own rule exactly.
        if "routing_group" in payload or "min_ratio" in payload:
            new_group = payload.get("routing_group", rule.routing_group)
            new_ratio = payload.get("min_ratio", float(rule.min_ratio))
            self._ensure_no_duplicate(rule.test_id, new_group, new_ratio, exclude_id=rule.id)
        self.repo.update(rule, payload)
        log_action(self.repo.db, action="routing_threshold_rule.updated", user_id=actor_id, entity_type="routing_threshold_rule", entity_id=rule.id)
        self.repo.commit()
        return rule

    def delete_rule(self, rule_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        """Soft delete — matches ExamSection/ExamModule/QuestionGroup's
        own convention. A soft-deleted rule is immediately excluded from
        RoutingThresholdRuleRepository.list_for_test(), the exact method
        ModuleExecutionService._select_routing_strategy() calls — so a
        deleted rule can never influence a live routing decision, with
        no change needed to the execution-side code at all."""
        rule = self.get_rule(rule_id)
        self.repo.soft_delete(rule)
        log_action(self.repo.db, action="routing_threshold_rule.deleted", user_id=actor_id, entity_type="routing_threshold_rule", entity_id=rule.id)
        self.repo.commit()
