"""Data-access layer for AiChat, AiHistoryEntry, AiRecommendation,
StudyPlan — four repositories in one file, same cohesive-module
reasoning as questions/repository.py."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ai.constants import MAX_HISTORY_MESSAGES_FOR_CONTEXT
from app.modules.ai.models import AiChat, AiHistoryEntry, AiRecommendation, StudyPlan


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, chat_id: uuid.UUID) -> AiChat | None:
        stmt = select(AiChat).where(AiChat.id == chat_id, AiChat.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID, page: int, per_page: int) -> tuple[list[AiChat], int]:
        stmt = select(AiChat).where(AiChat.user_id == user_id, AiChat.deleted_at.is_(None))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(AiChat.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def create(self, chat: AiChat) -> AiChat:
        self.db.add(chat)
        self.db.flush()
        return chat

    def commit(self) -> None:
        self.db.commit()


class HistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_chat(self, chat_id: uuid.UUID) -> list[AiHistoryEntry]:
        stmt = select(AiHistoryEntry).where(
            AiHistoryEntry.chat_id == chat_id, AiHistoryEntry.deleted_at.is_(None)
        ).order_by(AiHistoryEntry.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())

    def list_recent_for_context(self, chat_id: uuid.UUID) -> list[AiHistoryEntry]:
        """Most recent N messages, oldest-first — bounded so an
        ever-growing conversation doesn't send unbounded context to a
        future real provider."""
        stmt = select(AiHistoryEntry).where(
            AiHistoryEntry.chat_id == chat_id, AiHistoryEntry.deleted_at.is_(None)
        ).order_by(AiHistoryEntry.created_at.desc()).limit(MAX_HISTORY_MESSAGES_FOR_CONTEXT)
        rows = list(self.db.execute(stmt).scalars().all())
        return list(reversed(rows))

    def create(self, entry: AiHistoryEntry) -> AiHistoryEntry:
        self.db.add(entry)
        self.db.flush()
        return entry


class RecommendationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_user(self, user_id: uuid.UUID) -> list[AiRecommendation]:
        stmt = select(AiRecommendation).where(
            AiRecommendation.user_id == user_id, AiRecommendation.deleted_at.is_(None)
        ).order_by(AiRecommendation.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())


class StudyPlanRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, plan_id: uuid.UUID) -> StudyPlan | None:
        stmt = select(StudyPlan).where(StudyPlan.id == plan_id, StudyPlan.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID) -> list[StudyPlan]:
        stmt = select(StudyPlan).where(StudyPlan.user_id == user_id, StudyPlan.deleted_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def create(self, plan: StudyPlan) -> StudyPlan:
        self.db.add(plan)
        self.db.flush()
        return plan

    def commit(self) -> None:
        self.db.commit()
