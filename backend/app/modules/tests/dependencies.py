"""FastAPI dependency wiring for the tests module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.grades.repository import GradeRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.tests.repository import (
    ExamModuleRepository,
    ExamSectionRepository,
    QuestionGroupRepository,
    RoutingThresholdRuleRepository,
    TestRepository,
)
from app.modules.tests.service import (
    ExamModuleService,
    ExamSectionService,
    QuestionGroupService,
    RoutingThresholdRuleService,
    TestService,
)
from app.modules.topics.repository import TopicRepository


def get_test_repository(db: Session = Depends(get_db)) -> TestRepository:
    return TestRepository(db)


def get_test_service(
    repo: TestRepository = Depends(get_test_repository),
    db: Session = Depends(get_db),
) -> TestService:
    return TestService(repo, SubjectRepository(db), GradeRepository(db), TopicRepository(db))


def get_exam_section_repository(db: Session = Depends(get_db)) -> ExamSectionRepository:
    return ExamSectionRepository(db)


def get_exam_module_repository(db: Session = Depends(get_db)) -> ExamModuleRepository:
    return ExamModuleRepository(db)


def get_question_group_repository(db: Session = Depends(get_db)) -> QuestionGroupRepository:
    return QuestionGroupRepository(db)


def get_exam_section_service(
    repo: ExamSectionRepository = Depends(get_exam_section_repository),
    test_repo: TestRepository = Depends(get_test_repository),
) -> ExamSectionService:
    return ExamSectionService(repo, test_repo)


def get_exam_module_service(
    repo: ExamModuleRepository = Depends(get_exam_module_repository),
    section_repo: ExamSectionRepository = Depends(get_exam_section_repository),
    test_repo: TestRepository = Depends(get_test_repository),
) -> ExamModuleService:
    return ExamModuleService(repo, section_repo, test_repo)


def get_question_group_service(
    repo: QuestionGroupRepository = Depends(get_question_group_repository),
    test_repo: TestRepository = Depends(get_test_repository),
    module_repo: ExamModuleRepository = Depends(get_exam_module_repository),
    section_repo: ExamSectionRepository = Depends(get_exam_section_repository),
) -> QuestionGroupService:
    return QuestionGroupService(repo, test_repo, module_repo, section_repo)


def get_routing_threshold_rule_repository(db: Session = Depends(get_db)) -> RoutingThresholdRuleRepository:
    return RoutingThresholdRuleRepository(db)


def get_routing_threshold_rule_service(
    repo: RoutingThresholdRuleRepository = Depends(get_routing_threshold_rule_repository),
    test_repo: TestRepository = Depends(get_test_repository),
) -> RoutingThresholdRuleService:
    return RoutingThresholdRuleService(repo, test_repo)
