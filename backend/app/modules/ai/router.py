"""
HTTP layer for /api/v1/ai/*. Every endpoint requires authentication, no
Admin-tier endpoints this sprint. POST /chats/{id}/messages is rate-
limited (10/minute per user, approved decision) via the
rate_limit_by_user() dependency (auth module). Sprint 88: returns a real
AI-generated response when AI_PROVIDER=anthropic is configured with a
real key; otherwise still returns 501 (honest, not faked) — see
app/modules/ai/README.md's "Real AI provider (Sprint 88)" section.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.ai.constants import MESSAGE_RATE_LIMIT_MAX_REQUESTS, MESSAGE_RATE_LIMIT_WINDOW_SECONDS
from app.modules.ai.dependencies import (
    get_ai_chat_service,
    get_recommendation_service,
    get_study_plan_service,
)
from app.modules.ai.schemas import (
    ChatDetailOut,
    ChatOut,
    HistoryEntryOut,
    MessageResponseOut,
    RecommendationOut,
    SendMessageRequest,
    StudyPlanCreateRequest,
    StudyPlanOut,
)
from app.modules.ai.service import AIChatService, RecommendationService, StudyPlanService
from app.modules.auth.dependencies import get_current_user, rate_limit_by_user
from app.modules.users.models import User

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/chats", status_code=status.HTTP_201_CREATED, summary="Start a new AI conversation")
def start_chat(
    title: str | None = None,
    service: AIChatService = Depends(get_ai_chat_service),
    user: User = Depends(get_current_user),
):
    chat = service.start_chat(user.id, title)
    return success_response(ChatOut.model_validate(chat), "Suhbat boshlandi.")


@router.get("/chats/me", summary="List my conversations")
def list_my_chats(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    service: AIChatService = Depends(get_ai_chat_service),
    user: User = Depends(get_current_user),
):
    items, total = service.list_my_chats(user.id, page, per_page)
    data = {
        "items": [ChatOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Suhbatlarim.")


@router.get("/chats/{chat_id}", summary="Get a conversation with its full history")
def get_chat(
    chat_id: uuid.UUID,
    service: AIChatService = Depends(get_ai_chat_service),
    user: User = Depends(get_current_user),
):
    chat = service.get_chat(chat_id, user.id)
    history = service.get_history(chat_id, user.id)
    detail = ChatDetailOut(**ChatOut.model_validate(chat).model_dump(), history=[HistoryEntryOut.model_validate(h) for h in history])
    return success_response(detail, "Suhbat.")


@router.post(
    "/chats/{chat_id}/messages",
    summary="Send a message and get an AI response",
    description=f"Rate-limited: {MESSAGE_RATE_LIMIT_MAX_REQUESTS} requests/{MESSAGE_RATE_LIMIT_WINDOW_SECONDS}s per user. "
                "Returns a real AI-generated response when a provider is configured "
                "(AI_PROVIDER=anthropic + a real AI_API_KEY); otherwise 501 Not Implemented "
                "(honest refusal — see app/modules/ai/README.md).",
)
def send_message(
    chat_id: uuid.UUID,
    data: SendMessageRequest,
    service: AIChatService = Depends(get_ai_chat_service),
    user: User = Depends(rate_limit_by_user(
        "ai_message", max_requests=MESSAGE_RATE_LIMIT_MAX_REQUESTS, window_seconds=MESSAGE_RATE_LIMIT_WINDOW_SECONDS
    )),
):
    user_msg, assistant_msg = service.send_message(chat_id, user.id, data.content)
    response = MessageResponseOut(
        chat_id=chat_id,
        user_message=HistoryEntryOut.model_validate(user_msg),
        assistant_message=HistoryEntryOut.model_validate(assistant_msg),
    )
    return success_response(response, "Javob olindi.")


@router.get("/recommendations/me", summary="My AI-generated recommendations")
def list_my_recommendations(
    service: RecommendationService = Depends(get_recommendation_service),
    user: User = Depends(get_current_user),
):
    items = service.list_mine(user.id)
    return success_response([RecommendationOut.model_validate(i) for i in items], "Tavsiyalarim.")


@router.get("/study-plans/me", summary="My study plans")
def list_my_study_plans(
    service: StudyPlanService = Depends(get_study_plan_service),
    user: User = Depends(get_current_user),
):
    items = service.list_mine(user.id)
    return success_response([StudyPlanOut.model_validate(i) for i in items], "O'quv rejalarim.")


@router.post("/study-plans", status_code=status.HTTP_201_CREATED, summary="Create a study plan")
def create_study_plan(
    data: StudyPlanCreateRequest,
    service: StudyPlanService = Depends(get_study_plan_service),
    user: User = Depends(get_current_user),
):
    plan = service.create(data, user.id)
    return success_response(StudyPlanOut.model_validate(plan), "O'quv rejasi yaratildi.")
