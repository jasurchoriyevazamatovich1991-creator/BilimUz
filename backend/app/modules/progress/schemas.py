"""Request/response schemas for the progress module."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class LessonProgressOut(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    completed_at: datetime

    model_config = {"from_attributes": True}


class MyProgressOut(BaseModel):
    """The single response used by BOTH the Dashboard (aggregate fields)
    and LessonDetailPage (checking `completed_lesson_ids` for the
    current lesson) — deliberately one small, unpaginated response
    rather than two separate endpoints, since a young platform's total
    lesson count is realistically small. Documented as a known future
    scaling limitation, not a paginated list, for Sprint 36's scope."""
    completed_lessons: int
    total_lessons: int
    percentage: float
    completed_lesson_ids: list[uuid.UUID]
