"""
HTTP layer for /api/v1/tests/*. List/get are public (browsing available
tests is part of the public catalog, same as subjects/grades/topics);
write endpoints require Admin, Super Admin, or Teacher.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.tests.dependencies import get_test_service
from app.modules.tests.schemas import (
    TestCreateRequest,
    TestListParams,
    TestOut,
    TestPublishRequest,
    TestUpdateRequest,
)
from app.modules.tests.service import TestService
from app.modules.users.models import User

router = APIRouter(prefix="/tests", tags=["Tests"])


@router.get(
    "",
    summary="List tests",
    description="Paginated, searchable, sortable, filterable (by subject_id, grade_id, topic_id, "
                "difficulty, status) list of tests. Public.",
)
def list_tests(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, description="Case-insensitive substring match on title"),
    subject_id: uuid.UUID | None = Query(default=None),
    grade_id: uuid.UUID | None = Query(default=None),
    topic_id: uuid.UUID | None = Query(default=None),
    difficulty: str | None = Query(default=None, description="easy, medium, or hard"),
    status_filter: str | None = Query(default=None, alias="status", description="draft, published, or archived"),
    sort: str = Query(default="-created_at"),
    service: TestService = Depends(get_test_service),
):
    params = TestListParams(
        page=page, per_page=per_page, search=search, subject_id=subject_id,
        grade_id=grade_id, topic_id=topic_id, difficulty=difficulty, status=status_filter, sort=sort,
    )
    items, total = service.list_tests(params)
    data = {
        "items": [TestOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Testlar ro'yxati.")


@router.get(
    "/{test_id}",
    summary="Get a test by ID",
    description="Returns test metadata (not its questions — see the questions module). 404 if not found.",
)
def get_test(test_id: uuid.UUID, service: TestService = Depends(get_test_service)):
    test = service.get_test(test_id)
    return success_response(TestOut.model_validate(test), "Test topildi.")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a test",
    description="Creates a test in 'draft' status. Must be published separately (see POST /{id}/publish) "
                "before it becomes visible to students. 422 if subject_id/grade_id/topic_id are invalid.",
)
def create_test(
    data: TestCreateRequest,
    service: TestService = Depends(get_test_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    test = service.create_test(data, actor_id=user.id)
    return success_response(TestOut.model_validate(test), "Test yaratildi.")


@router.patch(
    "/{test_id}",
    summary="Update a test",
    description="Updates test metadata. Does not change status — use POST /{id}/publish for that.",
)
def update_test(
    test_id: uuid.UUID,
    data: TestUpdateRequest,
    service: TestService = Depends(get_test_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    test = service.update_test(test_id, data, actor_id=user.id)
    return success_response(TestOut.model_validate(test), "Test yangilandi.")


@router.post(
    "/{test_id}/publish",
    summary="Publish a test",
    description="Transitions a test from 'draft' to 'published'. Requires at least one question. "
                "409 if the current status doesn't allow this transition.",
)
def publish_test(
    test_id: uuid.UUID,
    _data: TestPublishRequest = TestPublishRequest(),
    service: TestService = Depends(get_test_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    test = service.publish_test(test_id, actor_id=user.id)
    return success_response(TestOut.model_validate(test), "Test e'lon qilindi.")


@router.delete(
    "/{test_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a test",
    description="Marks a test as deleted (deleted_at set, status='archived').",
)
def delete_test(
    test_id: uuid.UUID,
    service: TestService = Depends(get_test_service),
    user: User = Depends(require_roles("Admin", "Super Admin", "Teacher")),
):
    service.delete_test(test_id, actor_id=user.id)
