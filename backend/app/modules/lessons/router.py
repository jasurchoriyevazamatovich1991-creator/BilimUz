"""
HTTP layer for /api/v1/lessons/*. Read endpoints public (a lesson's video/
PDF/content is part of the course a student is taking); write endpoints
require Admin, Super Admin, or Teacher — same access as topics.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.lessons.dependencies import get_lesson_service
from app.modules.lessons.schemas import LessonCreateRequest, LessonListParams, LessonOut, LessonUpdateRequest
from app.modules.lessons.service import LessonService
from app.modules.progress.dependencies import get_progress_service
from app.modules.progress.schemas import LessonProgressOut
from app.modules.progress.service import ProgressService
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


# --- Sprint 36: Student Progress / Lesson Completion ---
# Lives here (not in a separate lessons-progress sub-route) because
# completing IS an action on a lesson resource — matches REST
# convention. The underlying LessonProgress persistence still lives in
# its own progress module (see app/modules/progress/), imported here
# read/write-style exactly like any other cross-module service
# dependency already used throughout this project.

@router.post(
    "/{lesson_id}/complete",
    summary="Mark a lesson as completed (Student)",
    description="Idempotent — completing an already-completed lesson returns the existing progress "
                "record rather than creating a duplicate. user_id is always the authenticated caller, "
                "never a request parameter.",
)
def complete_lesson(
    lesson_id: uuid.UUID,
    progress_service: ProgressService = Depends(get_progress_service),
    user: User = Depends(get_current_user),
):
    progress = progress_service.complete_lesson(user.id, lesson_id)
    return success_response(LessonProgressOut.model_validate(progress), "Dars tugatilgan deb belgilandi.")
