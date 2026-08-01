"""
HTTP layer for /api/v1/grades/*. Read endpoints are public (grade list
is needed to populate registration/test-filter dropdowns before login);
write endpoints require Admin or Super Admin, same pattern as subjects/roles.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.grades.dependencies import get_grade_service
from app.modules.grades.schemas import GradeCreateRequest, GradeListParams, GradeOut, GradeUpdateRequest
from app.modules.grades.service import GradeService
from app.modules.users.models import User

router = APIRouter(prefix="/grades", tags=["Grades"])


@router.get(
    "",
    summary="List grades",
    description="Returns a paginated, searchable, sortable, filterable list of grades "
                "(e.g. '5-sinf', 'Attestatsiya', 'Abituriyent'). Public — no authentication required.",
)
def list_grades(
    page: int = Query(default=1, ge=1, description="Page number, 1-indexed"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    search: str | None = Query(default=None, description="Case-insensitive substring match on name"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status: active, inactive, archived"),
    sort: str = Query(default="name", description="Sort field, prefix with '-' for descending (e.g. -created_at)"),
    service: GradeService = Depends(get_grade_service),
):
    params = GradeListParams(page=page, per_page=per_page, search=search, status=status_filter, sort=sort)
    items, total = service.list_grades(params)
    data = {
        "items": [GradeOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Sinf/darajalar ro'yxati.")


@router.get(
    "/{grade_id}",
    summary="Get a grade by ID",
    description="Returns a single grade. 404 if not found or soft-deleted.",
)
def get_grade(grade_id: uuid.UUID, service: GradeService = Depends(get_grade_service)):
    grade = service.get_grade(grade_id)
    return success_response(GradeOut.model_validate(grade), "Sinf/daraja topildi.")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a grade",
    description="Creates a new grade. Requires Admin or Super Admin. Name must be unique (case-insensitive).",
)
def create_grade(
    data: GradeCreateRequest,
    service: GradeService = Depends(get_grade_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    grade = service.create_grade(data, actor_id=admin.id)
    return success_response(GradeOut.model_validate(grade), "Sinf/daraja yaratildi.")


@router.patch(
    "/{grade_id}",
    summary="Update a grade",
    description="Updates a grade's status. Name is immutable after creation. Requires Admin or Super Admin.",
)
def update_grade(
    grade_id: uuid.UUID,
    data: GradeUpdateRequest,
    service: GradeService = Depends(get_grade_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    grade = service.update_grade(grade_id, data, actor_id=admin.id)
    return success_response(GradeOut.model_validate(grade), "Sinf/daraja yangilandi.")


@router.delete(
    "/{grade_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a grade",
    description="Marks a grade as deleted (deleted_at set, status='archived'). Requires Admin or Super Admin.",
)
def delete_grade(
    grade_id: uuid.UUID,
    service: GradeService = Depends(get_grade_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    service.delete_grade(grade_id, actor_id=admin.id)
