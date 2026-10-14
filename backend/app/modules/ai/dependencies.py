"""FastAPI dependency wiring for the ai module."""
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_AI_API_KEY, Settings, get_settings
from app.db.session import get_db
from app.modules.ai.providers import AIProvider, AnthropicProvider, UnconfiguredAIProvider
from app.modules.ai.repository import ChatRepository, HistoryRepository, RecommendationRepository, StudyPlanRepository
from app.modules.ai.service import AIChatService, RecommendationService, StudyPlanService


def select_ai_provider(settings: Settings) -> AIProvider:
    """Sprint 88 — pure selection logic, deliberately separated from
    get_ai_provider() below so it can be unit-tested directly against
    hand-built Settings instances (same pattern as
    app/core/tests/test_config_production_validation.py's `_settings()`
    helper) without needing to juggle env vars or lru_cache invalidation.

    Fails safely to UnconfiguredAIProvider (honest 501, never a fake
    response) whenever real credentials aren't genuinely available:
    AI_PROVIDER="none" (default), or AI_PROVIDER="anthropic" but
    AI_API_KEY is still at its public placeholder default — attempting a
    real call with that key would only ever produce a confusing 401 from
    Anthropic instead of this project's own clear, honest error."""
    if settings.AI_PROVIDER == "anthropic" and settings.AI_API_KEY != DEFAULT_AI_API_KEY:
        return AnthropicProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            timeout_seconds=settings.AI_REQUEST_TIMEOUT_SECONDS,
        )
    return UnconfiguredAIProvider()


@lru_cache
def get_ai_provider() -> AIProvider:
    return select_ai_provider(get_settings())


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
