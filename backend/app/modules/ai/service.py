"""
Business logic for AI chats, recommendations, study plans. Usage logging
reuses the EXISTING core.audit.log_action() — no new logging mechanism,
per the approved decision to reuse audit_logs instead of a new table.
"""
import uuid

from app.core.audit import log_action
from app.modules.ai.exceptions import AIProviderNotConfiguredException, ChatNotFoundException, StudyPlanNotFoundException
from app.modules.ai.models import AiChat, AiHistoryEntry, StudyPlan
from app.modules.ai.providers import AIMessage, AIProvider, AIRequest
from app.modules.ai.repository import ChatRepository, HistoryRepository, RecommendationRepository, StudyPlanRepository
from app.modules.ai.schemas import StudyPlanCreateRequest


class AIChatService:
    def __init__(self, chat_repository: ChatRepository, history_repository: HistoryRepository, provider: AIProvider):
        self.chat_repo = chat_repository
        self.history_repo = history_repository
        self.provider = provider

    def start_chat(self, user_id: uuid.UUID, title: str | None) -> AiChat:
        chat = AiChat(user_id=user_id, title=title)
        self.chat_repo.create(chat)
        self.chat_repo.commit()
        return chat

    def get_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> AiChat:
        chat = self.chat_repo.get_by_id(chat_id)
        if chat is None or chat.user_id != user_id:
            raise ChatNotFoundException("Suhbat topilmadi")
        return chat

    def get_history(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> list[AiHistoryEntry]:
        self.get_chat(chat_id, user_id)  # ownership check
        return self.history_repo.list_for_chat(chat_id)

    def list_my_chats(self, user_id: uuid.UUID, page: int, per_page: int) -> tuple[list[AiChat], int]:
        return self.chat_repo.list_for_user(user_id, page, per_page)

    def send_message(self, chat_id: uuid.UUID, user_id: uuid.UUID, content: str) -> tuple[AiHistoryEntry, AiHistoryEntry]:
        self.get_chat(chat_id, user_id)  # ownership check
        prior = self.history_repo.list_recent_for_context(chat_id)
        request = AIRequest(prompt=content, history=[AIMessage(role=e.role, content=e.message) for e in prior])

        user_entry = self.history_repo.create(AiHistoryEntry(chat_id=chat_id, role="user", message=content))

        try:
            response = self.provider.generate(request)
        except AIProviderNotConfiguredException:
            log_action(self.chat_repo.db, action="ai.message_sent", user_id=user_id, metadata={
                "chat_id": str(chat_id), "status": "provider_not_configured",
            })
            self.chat_repo.commit()
            raise

        assistant_entry = self.history_repo.create(AiHistoryEntry(chat_id=chat_id, role="assistant", message=response.content))
        log_action(self.chat_repo.db, action="ai.message_sent", user_id=user_id, metadata={
            "chat_id": str(chat_id), "status": "success", "provider": response.provider,
            "model": response.model, "tokens_used": response.tokens_used,
        })
        self.chat_repo.commit()
        return user_entry, assistant_entry


class RecommendationService:
    def __init__(self, repository: RecommendationRepository):
        self.repo = repository

    def list_mine(self, user_id: uuid.UUID):
        return self.repo.list_for_user(user_id)


class StudyPlanService:
    def __init__(self, repository: StudyPlanRepository):
        self.repo = repository

    def create(self, data: StudyPlanCreateRequest, user_id: uuid.UUID) -> StudyPlan:
        plan = StudyPlan(
            user_id=user_id, subject_id=data.subject_id, plan=data.plan,
            start_date=data.start_date, end_date=data.end_date,
        )
        self.repo.create(plan)
        self.repo.commit()
        return plan

    def list_mine(self, user_id: uuid.UUID) -> list[StudyPlan]:
        return self.repo.list_for_user(user_id)

    def get(self, plan_id: uuid.UUID, user_id: uuid.UUID) -> StudyPlan:
        plan = self.repo.get_by_id(plan_id)
        if plan is None or plan.user_id != user_id:
            raise StudyPlanNotFoundException("O'quv rejasi topilmadi")
        return plan
