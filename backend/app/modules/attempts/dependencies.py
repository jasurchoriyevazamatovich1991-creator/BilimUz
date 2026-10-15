"""FastAPI dependency wiring for the attempts module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.attempts.module_execution_service import ModuleExecutionService
from app.modules.attempts.repository import AnswerRepository, AttemptModuleProgressRepository, AttemptRepository
from app.modules.attempts.service import AttemptService
from app.modules.catalog.dependencies import get_catalog_product_repository
from app.modules.catalog.repository import CatalogProductRepository
from app.modules.entitlements.dependencies import get_entitlement_repository
from app.modules.entitlements.repository import EntitlementRepository
from app.modules.entitlements.service import EntitlementService
from app.modules.questions.repository import OptionRepository, QuestionRepository
from app.modules.tests.repository import (
    ExamModuleRepository,
    ExamSectionRepository,
    QuestionGroupRepository,
    RoutingThresholdRuleRepository,
    TestRepository,
)


def get_attempt_repository(db: Session = Depends(get_db)) -> AttemptRepository:
    return AttemptRepository(db)


def get_answer_repository(db: Session = Depends(get_db)) -> AnswerRepository:
    return AnswerRepository(db)


def get_module_progress_repository(db: Session = Depends(get_db)) -> AttemptModuleProgressRepository:
    return AttemptModuleProgressRepository(db)


def get_exam_module_repository(db: Session = Depends(get_db)) -> ExamModuleRepository:
    return ExamModuleRepository(db)


def get_exam_section_repository(db: Session = Depends(get_db)) -> ExamSectionRepository:
    return ExamSectionRepository(db)


def get_question_group_repository(db: Session = Depends(get_db)) -> QuestionGroupRepository:
    return QuestionGroupRepository(db)


def get_routing_threshold_rule_repository(db: Session = Depends(get_db)) -> RoutingThresholdRuleRepository:
    return RoutingThresholdRuleRepository(db)


def get_module_execution_service(
    module_repo: ExamModuleRepository = Depends(get_exam_module_repository),
    progress_repo: AttemptModuleProgressRepository = Depends(get_module_progress_repository),
    routing_rule_repo: RoutingThresholdRuleRepository = Depends(get_routing_threshold_rule_repository),
    db: Session = Depends(get_db),
) -> ModuleExecutionService:
    # Sprint 75 — routing_rule_repo is now always wired for the real
    # FastAPI dependency path (production behavior), exactly as
    # module_repo/progress_repo already were since Sprint 50. This is
    # what lets _select_routing_strategy() actually find real
    # RoutingThresholdRule rows once a future sprint adds a way to
    # create them. Until then, list_for_test() always returns an empty
    # list for every existing test, so production behavior is unchanged.
    return ModuleExecutionService(
        module_repo, progress_repo, QuestionRepository(db), AnswerRepository(db), AttemptRepository(db),
        routing_rule_repo,
    )


def get_entitlement_service_for_attempts(
    entitlement_repo: EntitlementRepository = Depends(get_entitlement_repository),
    product_repo: CatalogProductRepository = Depends(get_catalog_product_repository),
) -> EntitlementService:
    return EntitlementService(entitlement_repo, product_repo)


def get_attempt_service(
    repo: AttemptRepository = Depends(get_attempt_repository),
    answer_repo: AnswerRepository = Depends(get_answer_repository),
    module_execution: ModuleExecutionService = Depends(get_module_execution_service),
    module_repo: ExamModuleRepository = Depends(get_exam_module_repository),
    section_repo: ExamSectionRepository = Depends(get_exam_section_repository),
    group_repo: QuestionGroupRepository = Depends(get_question_group_repository),
    entitlement_service: EntitlementService = Depends(get_entitlement_service_for_attempts),
    db: Session = Depends(get_db),
) -> AttemptService:
    # Sprint 50 — module_execution/module_repo are now always wired for
    # the real FastAPI dependency path (production behavior). This is
    # exactly what makes AttemptService.start_attempt()'s has_modules()
    # branch actually activate for modular tests. Non-modular tests are
    # STILL completely unaffected — has_modules() returns False for
    # them, so the branch body never runs regardless of these being set.
    # Sprint A (post-75) — section_repo wired the same way, for
    # AttemptService.get_module_for_attempt()'s section-name lookup.
    # Sprint 77 — group_repo wired the same way, for
    # get_attempt_detail()'s batched QuestionGroup/stimulus_text lookup.
    # Mock Test Entitlements feature — entitlement_service wired the
    # same way, for start_attempt()'s is_mock_test gate. A non-mock
    # test's start_attempt() call never reads it at all.
    return AttemptService(
        repo, answer_repo, TestRepository(db), QuestionRepository(db), OptionRepository(db),
        module_execution, module_repo, section_repo, group_repo, entitlement_service,
    )
