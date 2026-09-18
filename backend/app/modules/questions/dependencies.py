"""FastAPI dependency wiring for the questions module (Question, Option, Media)."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.questions.repository import MediaRepository, OptionRepository, QuestionRepository
from app.modules.questions.service import MediaService, OptionService, QuestionService
from app.modules.tests.repository import ExamModuleRepository, ExamSectionRepository, QuestionGroupRepository, TestRepository
from app.modules.uploads.repository import UploadRepository


def get_question_repository(db: Session = Depends(get_db)) -> QuestionRepository:
    return QuestionRepository(db)


def get_question_service(
    repo: QuestionRepository = Depends(get_question_repository),
    db: Session = Depends(get_db),
) -> QuestionService:
    # Sprint 52 — section/module/group repositories are now always
    # wired for the real FastAPI dependency path (production
    # behavior); this is what activates _validate_assignment_fields()
    # for real requests.
    return QuestionService(
        repo, TestRepository(db), ExamSectionRepository(db), ExamModuleRepository(db), QuestionGroupRepository(db),
    )


def get_option_repository(db: Session = Depends(get_db)) -> OptionRepository:
    return OptionRepository(db)


def get_option_service(
    repo: OptionRepository = Depends(get_option_repository),
    q_repo: QuestionRepository = Depends(get_question_repository),
) -> OptionService:
    return OptionService(repo, q_repo)


def get_media_repository(db: Session = Depends(get_db)) -> MediaRepository:
    return MediaRepository(db)


def get_media_service(
    repo: MediaRepository = Depends(get_media_repository),
    q_repo: QuestionRepository = Depends(get_question_repository),
    opt_repo: OptionRepository = Depends(get_option_repository),
    db: Session = Depends(get_db),
) -> MediaService:
    return MediaService(repo, q_repo, opt_repo, UploadRepository(db))
