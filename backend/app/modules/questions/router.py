"""
HTTP layer for /api/v1/questions/*. List/get require authentication (not
fully public like tests/topics — a question's correct answer must never
be exposed to an unauthenticated caller); write endpoints require Admin,
Super Admin, or Teacher.

IMPORTANT: this router's QuestionOut includes is_correct on every option
— it is for CONTENT AUTHORING only (Admin/Teacher browsing their own
question bank). The student-facing, answer-hidden view is served by the
`attempts` module's own schema (QuestionOutNoAnswers-equivalent), never
this one.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.questions.dependencies import (
    get_media_service,
    get_option_service,
    get_question_service,
)
from app.modules.questions.schemas import (
    MediaCreateRequest,
    MediaOut,
    OptionCreateRequest,
    OptionOut,
    OptionUpdateRequest,
    QuestionCreateRequest,
    QuestionListParams,
    QuestionOut,
    QuestionUpdateRequest,
)
from app.modules.questions.service import MediaService, OptionService, QuestionService
from app.modules.users.models import User

router = APIRouter(prefix="/questions", tags=["Questions"])


@router.get(
    "",
    summary="List questions",
    description="Paginated, filterable (by test_id, difficulty, status) list of questions, "
                "INCLUDING correct answers — content-authoring view only. Requires authentication.",
)
def list_questions(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    test_id: uuid.UUID | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="created_at"),
    service: QuestionService = Depends(get_question_service),
    _user: User = Depends(get_current_user),
):
    params = QuestionListParams(page=page, per_page=per_page, test_id=test_id, difficulty=difficulty, status=status_filter, sort=sort)
    items, total = service.list_questions(params)
    data = {
        "items": [QuestionOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Savollar ro'yxati.")


@router.get(
    "/{question_id}",
    summary="Get a question by ID",
    description="Returns a question with its options (including is_correct) and media. Requires authentication.",
)
def get_question(
    question_id: uuid.UUID,
    service: QuestionService = Depends(get_question_service),
    _user: User = Depends(get_current_user),
):
    question = service.get_question(question_id)
    return success_response(QuestionOut.model_validate(question), "Savol topildi.")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a question",
    description="Creates a question under a test, optionally with inline options. "
                "single_choice/true_false require exactly 1 correct option; multiple_choice requires at least 1; "
                "choice-type questions need at least 2 options total.",
)
def create_question(
    data: QuestionCreateRequest,
    service: QuestionService = Depends(get_question_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    question = service.create_question(data, actor_id=user.id)
    return success_response(QuestionOut.model_validate(question), "Savol yaratildi.")


@router.patch(
    "/{question_id}",
    summary="Update a question",
    description="Updates question_text, difficulty, score, explanation, or status.",
)
def update_question(
    question_id: uuid.UUID,
    data: QuestionUpdateRequest,
    service: QuestionService = Depends(get_question_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    question = service.update_question(question_id, data, actor_id=user.id)
    return success_response(QuestionOut.model_validate(question), "Savol yangilandi.")


@router.delete(
    "/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a question",
    description="Marks a question as deleted and decrements the parent test's question_count.",
)
def delete_question(
    question_id: uuid.UUID,
    service: QuestionService = Depends(get_question_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    service.delete_question(question_id, actor_id=user.id)


@router.post(
    "/{question_id}/options",
    status_code=status.HTTP_201_CREATED,
    summary="Add an option to a question",
    description="422 if this would give a single_choice/true_false question two correct answers.",
)
def add_option(
    question_id: uuid.UUID,
    data: OptionCreateRequest,
    service: OptionService = Depends(get_option_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    option = service.add_option(question_id, data, actor_id=user.id)
    return success_response(OptionOut.model_validate(option), "Variant qo'shildi.")


@router.patch(
    "/{question_id}/options/{option_id}",
    summary="Update an option",
    description="Updates option_text or is_correct.",
)
def update_option(
    question_id: uuid.UUID,
    option_id: uuid.UUID,
    data: OptionUpdateRequest,
    service: OptionService = Depends(get_option_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    option = service.update_option(option_id, data, actor_id=user.id)
    return success_response(OptionOut.model_validate(option), "Variant yangilandi.")


@router.delete(
    "/{question_id}/options/{option_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an option",
)
def delete_option(
    question_id: uuid.UUID,
    option_id: uuid.UUID,
    service: OptionService = Depends(get_option_service),
    _user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    service.delete_option(option_id)


@router.post(
    "/{question_id}/media",
    status_code=status.HTTP_201_CREATED,
    summary="Attach media to a question",
    description="media_type: image, audio, video, or formula. file_url must be an already-hosted http(s) URL.",
)
def add_media(
    question_id: uuid.UUID,
    data: MediaCreateRequest,
    service: MediaService = Depends(get_media_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    media = service.add_media(question_id, data, actor_id=user.id)
    return success_response(MediaOut.model_validate(media), "Media biriktirildi.")


@router.delete(
    "/{question_id}/media/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove media from a question",
)
def delete_media(
    question_id: uuid.UUID,
    media_id: uuid.UUID,
    service: MediaService = Depends(get_media_service),
    _user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    service.delete_media(media_id)
