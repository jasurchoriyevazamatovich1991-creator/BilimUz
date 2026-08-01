"""
HTTP layer for /api/v1/topics/*. Read endpoints public (browsing a
subject's topic list is part of the public course catalog); write
endpoints require Admin, Super Admin, or Teacher (teachers author content).
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.topics.dependencies import get_topic_service
from app.modules.topics.schemas import TopicCreateRequest, TopicListParams, TopicOut, TopicUpdateRequest
from app.modules.topics.service import TopicService
from app.modules.users.models import User

router = APIRouter(prefix="/topics", tags=["Topics"])


@router.get(
    "",
    summary="List topics",
    description="Paginated, searchable, sortable, filterable (by subject_id, grade_id, status) list of topics. Public.",
)
def list_topics(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, description="Case-insensitive substring match on title"),
    subject_id: uuid.UUID | None = Query(default=None, description="Filter by parent subject"),
    grade_id: uuid.UUID | None = Query(default=None, description="Filter by grade/level"),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="order_number", description="Sort field, prefix '-' for descending"),
    service: TopicService = Depends(get_topic_service),
):
    params = TopicListParams(
        page=page, per_page=per_page, search=search,
        subject_id=subject_id, grade_id=grade_id, status=status_filter, sort=sort,
    )
    items, total = service.list_topics(params)
    data = {
        "items": [TopicOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Mavzular ro'yxati.")


@router.get(
    "/{topic_id}",
    summary="Get a topic by ID",
    description="Returns a single topic. 404 if not found or soft-deleted.",
)
def get_topic(topic_id: uuid.UUID, service: TopicService = Depends(get_topic_service)):
    topic = service.get_topic(topic_id)
    return success_response(TopicOut.model_validate(topic), "Mavzu topildi.")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a topic",
    description="Creates a topic under a subject (required) and optionally a grade. "
                "422 if subject_id or grade_id don't reference existing rows.",
)
def create_topic(
    data: TopicCreateRequest,
    service: TopicService = Depends(get_topic_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    topic = service.create_topic(data, actor_id=user.id)
    return success_response(TopicOut.model_validate(topic), "Mavzu yaratildi.")


@router.patch(
    "/{topic_id}",
    summary="Update a topic",
    description="Updates title, description, order_number, grade_id, or status.",
)
def update_topic(
    topic_id: uuid.UUID,
    data: TopicUpdateRequest,
    service: TopicService = Depends(get_topic_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    topic = service.update_topic(topic_id, data, actor_id=user.id)
    return success_response(TopicOut.model_validate(topic), "Mavzu yangilandi.")


@router.delete(
    "/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a topic",
    description="Marks a topic as deleted. Its lessons remain in the database (not cascade-deleted).",
)
def delete_topic(
    topic_id: uuid.UUID,
    service: TopicService = Depends(get_topic_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    service.delete_topic(topic_id, actor_id=user.id)
