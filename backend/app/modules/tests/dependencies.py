"""FastAPI dependency wiring for the tests module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.grades.repository import GradeRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.tests.repository import (
    ExamModuleRepository,
    ExamSectionRepository,
    QuestionGroupMediaRepository,
    QuestionGroupRepository,
    RoutingThresholdRuleRepository,
    ScoreConversionTableRepository,
    TestRepository,
)
from app.modules.tests.service import (
    ExamModuleService,
    ExamScoringService,
    ExamSectionService,
    QuestionGroupMediaService,
    QuestionGroupService,
    RoutingThresholdRuleService,
    TestService,
)
from app.modules.topics.repository import TopicRepository
from app.modules.uploads.repository import UploadRepository


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
    db: Session = Depends(get_db),
) -> ExamSectionService:
    return ExamSectionService(repo, test_repo, ScoreConversionTableRepository(db))


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


def get_question_group_media_service(db: Session = Depends(get_db)) -> QuestionGroupMediaService:
    """Task 3."""
    return QuestionGroupMediaService(QuestionGroupMediaRepository(db), QuestionGroupRepository(db), UploadRepository(db))


def get_exam_scoring_service(db: Session = Depends(get_db)) -> ExamScoringService:
    """Task 4."""
    return ExamScoringService(TestRepository(db), ExamSectionRepository(db), ExamModuleRepository(db), ScoreConversionTableRepository(db))
