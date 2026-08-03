"""FastAPI dependency wiring for the ai module."""
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.ai.providers import AIProvider, UnconfiguredAIProvider
from app.modules.ai.repository import ChatRepository, HistoryRepository, RecommendationRepository, StudyPlanRepository
from app.modules.ai.service import AIChatService, RecommendationService, StudyPlanService


@lru_cache
def get_ai_provider() -> AIProvider:
    return UnconfiguredAIProvider()


def get_chat_repository(db: Session = Depends(get_db)) -> ChatRepository:
    return ChatRepository(db)


def get_history_repository(db: Session = Depends(get_db)) -> HistoryRepository:
    return HistoryRepository(db)


def get_ai_chat_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    history_repo: HistoryRepository = Depends(get_history_repository),
    provider: AIProvider = Depends(get_ai_provider),
) -> AIChatService:
    return AIChatService(chat_repo, history_repo, provider)


def get_recommendation_repository(db: Session = Depends(get_db)) -> RecommendationRepository:
    return RecommendationRepository(db)


def get_recommendation_service(repo: RecommendationRepository = Depends(get_recommendation_repository)) -> RecommendationService:
    return RecommendationService(repo)


def get_study_plan_repository(db: Session = Depends(get_db)) -> StudyPlanRepository:
    return StudyPlanRepository(db)


def get_study_plan_service(repo: StudyPlanRepository = Depends(get_study_plan_repository)) -> StudyPlanService:
    return StudyPlanService(repo)
