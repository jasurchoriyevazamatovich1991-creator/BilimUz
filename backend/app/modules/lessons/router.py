"""
HTTP layer for /api/v1/lessons/*. Read endpoints public (a lesson's video/
PDF/content is part of the course a student is taking); write endpoints
require Admin, Super Admin, or Teacher — same access as topics.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.lessons.dependencies import get_lesson_service
from app.modules.lessons.schemas import LessonCreateRequest, LessonListParams, LessonOut, LessonUpdateRequest
from app.modules.lessons.service import LessonService
from app.modules.users.models import User

router = APIRouter(prefix="/lessons", tags=["Lessons"])


@router.get(
    "",
    summary="List lessons",
    description="Paginated, searchable, sortable, filterable (by topic_id, status) list of lessons. Public.",
)
def list_lessons(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, description="Case-insensitive substring match on title"),
    topic_id: uuid.UUID | None = Query(default=None, description="Filter by parent topic"),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="-created_at", description="Sort field, prefix '-' for descending"),
    service: LessonService = Depends(get_lesson_service),
):
    params = LessonListParams(
        page=page, per_page=per_page, search=search, topic_id=topic_id, status=status_filter, sort=sort,
    )
    items, total = service.list_lessons(params)
    data = {
        "items": [LessonOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Darslar ro'yxati.")


@router.get(
    "/{lesson_id}",
    summary="Get a lesson by ID",
    description="Returns a single lesson (video/pdf/content). 404 if not found or soft-deleted.",
)
def get_lesson(lesson_id: uuid.UUID, service: LessonService = Depends(get_lesson_service)):
    lesson = service.get_lesson(lesson_id)
    return success_response(LessonOut.model_validate(lesson), "Dars topildi.")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a lesson",
    description="Creates a lesson under a topic. Must include at least one of: video, pdf, content. "
                "422 if topic_id doesn't reference an existing topic.",
)
def create_lesson(
    data: LessonCreateRequest,
    service: LessonService = Depends(get_lesson_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    lesson = service.create_lesson(data, actor_id=user.id)
    return success_response(LessonOut.model_validate(lesson), "Dars yaratildi.")


@router.patch(
    "/{lesson_id}",
    summary="Update a lesson",
    description="Updates title, video, pdf, content, or status. Rejected if the update would "
                "leave the lesson with no content at all (no video, pdf, or content).",
)
def update_lesson(
    lesson_id: uuid.UUID,
    data: LessonUpdateRequest,
    service: LessonService = Depends(get_lesson_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    lesson = service.update_lesson(lesson_id, data, actor_id=user.id)
    return success_response(LessonOut.model_validate(lesson), "Dars yangilandi.")


@router.delete(
    "/{lesson_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a lesson",
    description="Marks a lesson as deleted (deleted_at set, status='archived').",
)
def delete_lesson(
    lesson_id: uuid.UUID,
    service: LessonService = Depends(get_lesson_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    service.delete_lesson(lesson_id, actor_id=user.id)
