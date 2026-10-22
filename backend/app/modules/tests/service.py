"""
Business logic for test management. Validates subject_id/grade_id/topic_id
references using existing, unmodified repositories (read-only reuse, same
pattern as topics → subjects/grades). Enforces the publish-readiness rule
and status-transition rules described in
docs/Sprint6_TestEngine_Architecture.md Section 11.
"""
import uuid
from datetime import date

from app.core.audit import log_action
from app.modules.grades.repository import GradeRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.tests.exceptions import (
    DuplicateGroupMediaException,
    GroupMediaUploadNotReadyException,
    QuestionGroupMediaNotFoundException,
    UnsupportedGroupMediaTypeException,
    UploadNotFoundForGroupMediaException,
    CannotPublishEmptyTestException,
    DuplicateOrderNumberException,
    DuplicateRoutingThresholdRuleException,
    ExamModuleNotFoundException,
    ExamSectionNotFoundException,
    InvalidScoringConfigurationException,
    InvalidStatusTransitionException,
    InvalidTestReferenceException,
    ScoringConfigurationConflictException,
    MockTestRequiresSubjectException,
    QuestionGroupNotFoundException,
    RoutingThresholdRuleNotFoundException,
    TestNotFoundException,
)
from app.modules.tests.models import ExamModule, ExamSection, QuestionGroup, QuestionGroupMedia, RoutingThresholdRule, ScoreConversionTable, Test, TestStatus
from app.modules.tests.repository import (
    ExamModuleRepository,
    ExamSectionRepository,
    QuestionGroupMediaRepository,
    QuestionGroupRepository,
    RoutingThresholdRuleRepository,
    ScoreConversionTableRepository,
    TestRepository,
)
from app.modules.tests.schemas import (
    ConversionTableCreateRequest,
    ConversionTableEntryIn,
    ExamModuleCreateRequest,
    ExamModuleUpdateRequest,
    ExamSectionCreateRequest,
    ExamSectionUpdateRequest,
    QuestionGroupCreateRequest,
    QuestionGroupMediaCreateRequest,
    QuestionGroupUpdateRequest,
    RoutingThresholdRuleCreateRequest,
    RoutingThresholdRuleUpdateRequest,
    TestCreateRequest,
    TestListParams,
    TestUpdateRequest,
)
from app.modules.results.scaled_scoring import (
    COMPONENTS,
    SCORING_PROFILES,
    METHOD_RANGE,
    PROFILE_IELTS,
    InvalidConversionTable,
    validate_conversion_table,
)
from app.modules.results.official_scoring import (
    CONVERSION_TYPES,
    IELTS_MODULES,
    OFFICIAL_TABLE_PROFILES,
    PRACTICE_FORMS,
    TABLE_OFFICIAL_PRACTICE_TEST,
    official_practice_table,
    source_anomaly_notes,
)
from app.modules.uploads.constants import UPLOAD_STATUS_PENDING
from app.modules.uploads.repository import UploadRepository
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
        # Schema-level model_validator already rejects this for a full
        # create request — kept here too (cheap, same check) so the
        # same guarantee holds even if a caller builds a TestCreateRequest
        # programmatically and skips Pydantic validation somehow.
        self._validate_mock_test_consistency(data.is_mock_test, data.subject_id)

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
            is_mock_test=data.is_mock_test,
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
        # Partial update — merge onto the EXISTING row before checking,
        # not just the submitted fields. Covers both directions: turning
        # is_mock_test on without ever submitting a subject_id (falls
        # back to the test's current one, which may itself be None), and
        # clearing subject_id on a test that is already a mock test.
        self._validate_mock_test_consistency(
            updates.get("is_mock_test", test.is_mock_test),
            updates.get("subject_id", test.subject_id),
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

    def _validate_mock_test_consistency(self, is_mock_test: bool, subject_id: uuid.UUID | None) -> None:
        """Mirrors ck_tests_mock_test_requires_subject (migration 0021)
        — a mock test is exactly what EntitlementService.has_mock_test_access
        keys on via subject_id, so one can never exist without the other."""
        if is_mock_test and subject_id is None:
            raise MockTestRequiresSubjectException(
                "is_mock_test=true uchun subject_id (fan/yo'nalish) ko'rsatilishi shart"
            )


class ExamSectionService:
    """Sprint 51 — Admin Configuration API for ExamSection (Sprint 45).
    Mirrors TestService's own validation style (existence checks via
    the already-existing repositories, clean domain exceptions instead
    of raw IntegrityError)."""

    def __init__(self, repo: ExamSectionRepository, test_repo: TestRepository, table_repo: ScoreConversionTableRepository | None = None):
        self.repo = repo
        self.test_repo = test_repo
        # Task 4 — optional (pre-Task-4 constructions keep working); used
        # only to refuse a score_component change once tables exist.
        self.table_repo = table_repo

    def _validate_score_component(self, test, component: str | None, exclude_id: uuid.UUID | None = None) -> None:
        """Task 4 — a section's component must belong to its test's
        scoring_profile and be unique among the test's active sections."""
        if component is None:
            return
        spec = COMPONENTS.get(component)
        if spec is None:
            raise InvalidScoringConfigurationException(f"score_component quyidagilardan biri bo'lishi kerak: {', '.join(COMPONENTS)}")
        if test.scoring_profile is None:
            raise InvalidScoringConfigurationException("Avval testga ballash profili (IELTS/SAT/GRE) belgilanishi kerak")
        if spec.profile != test.scoring_profile:
            raise InvalidScoringConfigurationException(
                f"'{component}' komponenti '{test.scoring_profile}' profiliga tegishli emas"
            )
        for existing in self.repo.list_for_test(test.id):
            if existing.score_component == component and existing.id != exclude_id:
                raise InvalidScoringConfigurationException(f"Bu testda '{component}' komponentli bo'lim allaqachon bor")

    def _ensure_no_duplicate_order(self, test_id: uuid.UUID, order_number: int, exclude_id: uuid.UUID | None = None) -> None:
        for existing in self.repo.list_for_test(test_id):
            if existing.order_number == order_number and existing.id != exclude_id:
                raise DuplicateOrderNumberException(f"Bu test uchun order_number={order_number} allaqachon band")

    def create_section(self, data: ExamSectionCreateRequest, actor_id: uuid.UUID) -> ExamSection:
        test = self.test_repo.get_by_id(data.test_id)
        if test is None:
            raise InvalidTestReferenceException("Ko'rsatilgan test (test_id) mavjud emas")
        self._ensure_no_duplicate_order(data.test_id, data.order_number)
        self._validate_score_component(test, data.score_component)

        section = ExamSection(
            test_id=data.test_id, name=data.name, order_number=data.order_number, duration=data.duration,
            score_component=data.score_component, calculator_enabled=data.calculator_enabled,
        )
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
        if payload.get("calculator_enabled", False) is None:
            payload.pop("calculator_enabled")  # null = leave unchanged (column is NOT NULL)
        if "order_number" in payload:
            self._ensure_no_duplicate_order(section.test_id, payload["order_number"], exclude_id=section.id)
        if "score_component" in payload and payload["score_component"] != section.score_component:
            if self.table_repo is not None and self.table_repo.has_any(section.id):
                raise ScoringConfigurationConflictException(
                    "Bu bo'limga konversiya jadvallari biriktirilgan — komponentni o'zgartirib bo'lmaydi"
                )
            self._validate_score_component(self.test_repo.get_by_id(section.test_id), payload["score_component"], exclude_id=section.id)
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


GROUP_MEDIA_FILE_TYPES = ("audio", "image")


class QuestionGroupMediaService:
    """Task 3 — attach/remove media on a QuestionGroup (Admin/Super Admin,
    the same roles as group CRUD). Reads UploadRepository read-only, the
    same cross-module read questions/service.py already does for
    question media."""

    def __init__(self, repo: QuestionGroupMediaRepository, group_repo: QuestionGroupRepository, upload_repo: UploadRepository):
        self.repo = repo
        self.group_repo = group_repo
        self.upload_repo = upload_repo

    def _active_group(self, group_id: uuid.UUID) -> QuestionGroup:
        group = self.group_repo.get_active_by_id(group_id)
        if group is None:
            raise QuestionGroupNotFoundException("Savol guruhi topilmadi")
        return group

    def add_media(self, group_id: uuid.UUID, data: QuestionGroupMediaCreateRequest, actor_id: uuid.UUID) -> QuestionGroupMedia:
        self._active_group(group_id)
        upload = self.upload_repo.get_by_id(data.upload_id)
        if upload is None:
            raise UploadNotFoundForGroupMediaException("Ko'rsatilgan fayl (upload_id) topilmadi")
        if upload.file_type not in GROUP_MEDIA_FILE_TYPES:
            raise UnsupportedGroupMediaTypeException("Guruhga faqat audio yoki rasm fayli biriktirish mumkin")
        if upload.status == UPLOAD_STATUS_PENDING:
            raise GroupMediaUploadNotReadyException("Fayl yuklanishi hali yakunlanmagan")
        if self.repo.find_active(group_id, upload.id) is not None:
            raise DuplicateGroupMediaException("Bu fayl ushbu guruhga allaqachon biriktirilgan")

        media = QuestionGroupMedia(group_id=group_id, upload_id=upload.id, media_type=upload.file_type, created_by=actor_id)
        self.repo.create(media)
        log_action(self.repo.db, action="question_group.media_added", user_id=actor_id, entity_type="question_group", entity_id=group_id)
        self.repo.commit()
        return media

    def remove_media(self, group_id: uuid.UUID, media_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        self._active_group(group_id)
        media = self.repo.get_active_by_id(media_id)
        if media is None or media.group_id != group_id:
            raise QuestionGroupMediaNotFoundException("Guruh mediasi topilmadi")
        self.repo.soft_delete(media, actor_id)
        log_action(self.repo.db, action="question_group.media_removed", user_id=actor_id, entity_type="question_group", entity_id=group_id)
        self.repo.commit()


class ExamScoringService:
    """Task 4 — Admin/Super Admin configuration of exam-specific scaled
    scoring: a test's scoring profile and its sections' versioned
    raw-to-scaled conversion tables. Validation rules live in the pure
    results/scaled_scoring module."""

    def __init__(
        self, test_repo: TestRepository, section_repo: ExamSectionRepository,
        module_repo: ExamModuleRepository, table_repo: ScoreConversionTableRepository,
    ):
        self.test_repo = test_repo
        self.section_repo = section_repo
        self.module_repo = module_repo
        self.table_repo = table_repo

    def set_scoring_profile(self, test_id: uuid.UUID, profile: str | None, actor_id: uuid.UUID,
                            ielts_module: str | None = None, ielts_module_given: bool = False) -> Test:
        test = self.test_repo.get_by_id(test_id)
        if test is None or test.deleted_at is not None:
            raise TestNotFoundException("Test topilmadi")
        if profile is not None and profile not in SCORING_PROFILES:
            raise InvalidScoringConfigurationException(f"scoring_profile quyidagilardan biri bo'lishi kerak: {', '.join(SCORING_PROFILES)}")
        if profile != test.scoring_profile:
            mismatched = [
                s.name for s in self.section_repo.list_for_test(test.id)
                if s.score_component is not None and COMPONENTS[s.score_component].profile != profile
            ]
            if mismatched:
                raise ScoringConfigurationConflictException(
                    "Avval bu bo'limlarning ballash komponentini olib tashlang: " + ", ".join(mismatched)
                )
        # Task 7 — Academic vs General Training (IELTS only).
        if profile != PROFILE_IELTS:
            if ielts_module_given and ielts_module is not None:
                raise InvalidScoringConfigurationException("ielts_module faqat IELTS profili uchun")
            new_module = None
        elif ielts_module_given:
            if ielts_module is not None and ielts_module not in IELTS_MODULES:
                raise InvalidScoringConfigurationException(f"ielts_module quyidagilardan biri bo'lishi kerak: {', '.join(IELTS_MODULES)}")
            new_module = ielts_module
        else:
            new_module = test.ielts_module if test.scoring_profile == PROFILE_IELTS else None
        test.scoring_profile = profile
        test.ielts_module = new_module
        test.updated_by = actor_id
        self.test_repo.db.flush()
        log_action(self.test_repo.db, action="test.scoring_profile_set", user_id=actor_id, entity_type="test", entity_id=test.id,
                   metadata={"scoring_profile": profile, "ielts_module": new_module})
        self.test_repo.db.commit()
        return test

    def _active_section(self, section_id: uuid.UUID) -> ExamSection:
        section = self.section_repo.get_by_id(section_id)
        if section is None or section.deleted_at is not None:
            raise ExamSectionNotFoundException("Bo'lim topilmadi")
        return section

    def list_tables(self, section_id: uuid.UUID) -> list[tuple[ScoreConversionTable, bool]]:
        self._active_section(section_id)
        tables = self.table_repo.list_for_section(section_id)
        current: dict = {}
        for t in tables:
            key = t.routing_variant
            if key not in current or t.version > current[key].version:
                current[key] = t
        current_ids = {t.id for t in current.values()}
        return [(t, t.id in current_ids) for t in tables]

    def _provenance(self, test: Test, section: ExamSection, data: ConversionTableCreateRequest) -> dict:
        """Task 7 — validates and returns the table's provenance columns.

        'official_practice_test' is only accepted for an exam whose official
        practice-test conversions are registered (SAT), with a registered
        test_form of that exam, the 'range' method the guides use, and no
        routing_variant (the paper-guide table covers the whole section).
        All official tables of one test must name the same form, so tables
        of different practice tests are never mixed. Its source URL/title
        come from the registry, not the request."""
        ctype = data.conversion_type
        if ctype not in CONVERSION_TYPES:
            raise InvalidScoringConfigurationException(f"conversion_type quyidagilardan biri bo'lishi kerak: {', '.join(CONVERSION_TYPES)}")
        if ctype != TABLE_OFFICIAL_PRACTICE_TEST:
            if data.test_form is not None:
                raise InvalidScoringConfigurationException("test_form faqat 'official_practice_test' jadvali uchun")
            return {
                "conversion_type": ctype, "test_form": None,
                "source_url": data.source_url, "source_title": data.source_title,
                "source_version": data.source_version, "source_verified_at": data.source_verified_at,
            }
        if test.scoring_profile not in OFFICIAL_TABLE_PROFILES:
            raise InvalidScoringConfigurationException(
                "Bu imtihon uchun rasmiy konversiya jadvali tasdiqlanmagan (IELTS: faqat indikativ, GRE: ETS jadval chop etmaydi) — "
                "'estimate' turidan foydalaning"
            )
        form = PRACTICE_FORMS.get(data.test_form or "")
        if form is None or form.exam != test.scoring_profile:
            raise InvalidScoringConfigurationException("test_form ro'yxatdagi rasmiy amaliy test bo'lishi kerak (masalan sat_practice_test_4)")
        if data.method != METHOD_RANGE:
            raise InvalidScoringConfigurationException("Rasmiy SAT amaliy test jadvali 'range' (lower/upper) usulida kiritiladi")
        if data.routing_variant is not None:
            raise InvalidScoringConfigurationException("Rasmiy amaliy test jadvali butun bo'lim uchun — routing_variant qo'yilmaydi")
        # Task 8 — the guides score the paper (nonadaptive) form; a section
        # whose modules route students adaptively is a different exam.
        if any(m.routing_variant for m in self.module_repo.list_for_section(section.id)):
            raise InvalidScoringConfigurationException(
                "Rasmiy jadval paper (nonadaptive) amaliy test uchun — adaptiv (routing variantli) bo'limga qo'llanmaydi"
            )
        for other in self.section_repo.list_for_test(test.id):
            for variant in {None} | {m.routing_variant for m in self.module_repo.list_for_section(other.id) if m.routing_variant}:
                current = self.table_repo.get_current(other.id, variant)
                if current is not None and current.conversion_type == TABLE_OFFICIAL_PRACTICE_TEST and current.test_form != form.form_id:
                    raise ScoringConfigurationConflictException(
                        f"Bu testda boshqa amaliy test ({current.test_form}) jadvali bor — turli formalar aralashtirilmaydi"
                    )
        # Task 8 — provenance comes entirely from the verified dataset.
        return {
            "conversion_type": ctype, "test_form": form.form_id,
            "source_url": form.scoring_guide_url, "source_title": f"{form.guide_title} — {form.label}",
            "source_version": f"{form.document_code} (© {form.copyright_year} College Board)",
            "source_verified_at": date.fromisoformat(form.verified_at),
        }

    def publish_table(self, section_id: uuid.UUID, data: ConversionTableCreateRequest, actor_id: uuid.UUID) -> ScoreConversionTable:
        self._active_section(section_id)
        section = self.table_repo.lock_section(section_id)
        if section is None:
            raise ExamSectionNotFoundException("Bo'lim topilmadi")
        test = self.test_repo.get_by_id(section.test_id)
        if test is None or test.scoring_profile is None:
            raise InvalidScoringConfigurationException("Avval testga ballash profili (IELTS/SAT/GRE) belgilanishi kerak")
        if section.score_component is None:
            raise InvalidScoringConfigurationException("Avval bo'limga ballash komponenti belgilanishi kerak")
        if data.routing_variant is not None:
            variants = {m.routing_variant for m in self.module_repo.list_for_section(section.id) if m.routing_variant}
            if data.routing_variant not in variants:
                raise InvalidScoringConfigurationException(
                    f"routing_variant='{data.routing_variant}' bu bo'limdagi hech bir modulda yo'q"
                )
        provenance = self._provenance(test, section, data)
        anomalies: frozenset = frozenset()
        if provenance["conversion_type"] == TABLE_OFFICIAL_PRACTICE_TEST:
            # Task 8 — the values are the verified College Board table for
            # this form and section; a request may omit them, and anything it
            # does send must match exactly (never a hand-typed variant).
            official = official_practice_table(provenance["test_form"], section.score_component)
            if official is None:
                raise InvalidScoringConfigurationException("Bu forma/bo'lim uchun tekshirilgan rasmiy jadval yo'q")
            verified_entries, anomalies = official
            if data.entries:
                sent = [{"raw": int(e.raw), "lower": int(e.lower), "upper": int(e.upper)}
                        if e.lower is not None and e.upper is not None and e.raw == int(e.raw) else None for e in data.entries]
                if sent != verified_entries:
                    raise InvalidScoringConfigurationException(
                        "Yuborilgan qiymatlar rasmiy scoring guide jadvaliga mos emas — qiymatlarni yubormang, ular manbadan olinadi"
                    )
            data = data.model_copy(update={"entries": [ConversionTableEntryIn(**e) for e in verified_entries]})
        elif not data.entries:
            raise InvalidScoringConfigurationException("Jadvalda kamida bitta qator bo'lishi kerak")
        if data.method == METHOD_RANGE:
            raw_entries = [{"raw": e.raw, "lower": e.lower, "upper": e.upper} for e in data.entries]
            if any(e.lower is None or e.upper is None for e in data.entries):
                raise InvalidScoringConfigurationException("'range' usulida har bir qatorda raw, lower va upper bo'lishi kerak")
        else:
            if any(e.scaled is None for e in data.entries):
                raise InvalidScoringConfigurationException("Har bir qatorda raw va scaled bo'lishi kerak")
            raw_entries = [{"raw": e.raw, "scaled": e.scaled} for e in data.entries]
        try:
            entries = validate_conversion_table(section.score_component, data.method, raw_entries, anomalies)
        except InvalidConversionTable as exc:
            raise InvalidScoringConfigurationException(str(exc))

        # Task 8 — no duplicate versions: re-publishing exactly the current
        # table (same data and provenance) would only add an ambiguous copy.
        current = self.table_repo.get_current(section.id, data.routing_variant)
        if current is not None and (
            current.method == data.method and current.entries == entries
            and current.conversion_type == provenance["conversion_type"] and current.test_form == provenance["test_form"]
        ):
            raise ScoringConfigurationConflictException(f"Bu jadval joriy {current.version}-versiya bilan bir xil — yangi versiya yaratilmadi")

        table = ScoreConversionTable(
            section_id=section.id, routing_variant=data.routing_variant,
            version=self.table_repo.max_version(section.id, data.routing_variant) + 1,
            method=data.method, entries=entries, created_by=actor_id, **provenance,
        )
        self.table_repo.create(table)
        log_action(self.table_repo.db, action="score_conversion_table.published", user_id=actor_id,
                   entity_type="exam_section", entity_id=section.id,
                   metadata={"table_id": str(table.id), "version": table.version, "routing_variant": data.routing_variant,
                             "conversion_type": provenance["conversion_type"], "test_form": provenance["test_form"],
                             # Task 8 — documented source anomalies kept as published.
                             "source_anomalies": source_anomaly_notes(provenance["test_form"], section.score_component)})
        self.table_repo.commit()
        return table
