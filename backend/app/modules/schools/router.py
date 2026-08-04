"""
HTTP layer for /api/v1/schools/*. Read endpoints public (a school
directory is browsable, like subjects/grades); write endpoints require
Admin or Super Admin.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.schools.dependencies import get_school_service
from app.modules.schools.schemas import SchoolCreateRequest, SchoolListParams, SchoolOut, SchoolUpdateRequest
from app.modules.schools.service import SchoolService
from app.modules.users.models import User

router = APIRouter(prefix="/schools", tags=["Schools"])


@router.get(
    "",
    summary="List schools",
    description="Paginated, searchable (by name), filterable (by region, district, status) list of schools. Public.",
)
def list_schools(
    page: int = Query(default=1, ge=1, description="Page number, 1-indexed"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    search: str | None = Query(default=None, description="Case-insensitive substring match on name"),
    region: str | None = Query(default=None),
    district: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", description="active, inactive, or archived"),
    sort: str = Query(default="name", description="Sort field, prefix '-' for descending"),
    service: SchoolService = Depends(get_school_service),
):
    params = SchoolListParams(page=page, per_page=per_page, search=search, region=region, district=district, status=status_filter, sort=sort)
    items, total = service.list_schools(params)
    data = {
        "items": [SchoolOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Maktablar ro'yxati.")


@router.get(
    "/{school_id}",
    summary="Get a school by ID",
    description="Returns a single school. 404 if not found or soft-deleted.",
)
def get_school(school_id: uuid.UUID, service: SchoolService = Depends(get_school_service)):
    school = service.get_school(school_id)
    return success_response(SchoolOut.model_validate(school), "Maktab topildi.")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a school",
    description="Creates a new school. Requires Admin or Super Admin. Name is not required to be unique "
                "(multiple schools in different regions may share a name).",
)
def create_school(
    data: SchoolCreateRequest,
    service: SchoolService = Depends(get_school_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    school = service.create_school(data, actor_id=admin.id)
    return success_response(SchoolOut.model_validate(school), "Maktab yaratildi.")


@router.patch(
    "/{school_id}",
    summary="Update a school",
    description="Updates any field including status. Requires Admin or Super Admin.",
)
def update_school(
    school_id: uuid.UUID,
    data: SchoolUpdateRequest,
    service: SchoolService = Depends(get_school_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    school = service.update_school(school_id, data, actor_id=admin.id)
    return success_response(SchoolOut.model_validate(school), "Maktab yangilandi.")


@router.delete(
    "/{school_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a school",
    description="Marks a school as deleted (deleted_at set, status='archived'). Requires Admin or Super Admin.",
)
def delete_school(
    school_id: uuid.UUID,
    service: SchoolService = Depends(get_school_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    service.delete_school(school_id, actor_id=admin.id)
