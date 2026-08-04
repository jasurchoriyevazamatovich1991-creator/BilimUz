"""
HTTP layer for /api/v1/learning-centers/*. Read endpoints public; write
endpoints require Admin or Super Admin. URL uses a hyphen
("learning-centers") per REST convention, while the Python module/table
name stays snake_case ("learning_centers", approved decision 3) — same
split already used elsewhere (e.g. certificate-templates URL vs.
certificate_templates table).
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.learning_centers.dependencies import get_learning_center_service
from app.modules.learning_centers.schemas import (
    LearningCenterCreateRequest,
    LearningCenterListParams,
    LearningCenterOut,
    LearningCenterUpdateRequest,
)
from app.modules.learning_centers.service import LearningCenterService
from app.modules.users.models import User

router = APIRouter(prefix="/learning-centers", tags=["Learning Centers"])


@router.get(
    "",
    summary="List learning centers",
    description="Paginated, searchable (by name or owner_name), filterable (by region, status). Public.",
)
def list_learning_centers(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, description="Case-insensitive substring match on name or owner_name"),
    region: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="name", description="Sort field, prefix '-' for descending"),
    service: LearningCenterService = Depends(get_learning_center_service),
):
    params = LearningCenterListParams(page=page, per_page=per_page, search=search, region=region, status=status_filter, sort=sort)
    items, total = service.list_centers(params)
    data = {
        "items": [LearningCenterOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "O'quv markazlari ro'yxati.")


@router.get(
    "/{center_id}",
    summary="Get a learning center by ID",
    description="Returns a single learning center. 404 if not found or soft-deleted.",
)
def get_learning_center(center_id: uuid.UUID, service: LearningCenterService = Depends(get_learning_center_service)):
    center = service.get_center(center_id)
    return success_response(LearningCenterOut.model_validate(center), "O'quv markazi topildi.")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a learning center",
    description="Creates a new learning center. Requires Admin or Super Admin. Name is not required to be unique.",
)
def create_learning_center(
    data: LearningCenterCreateRequest,
    service: LearningCenterService = Depends(get_learning_center_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    center = service.create_center(data, actor_id=admin.id)
    return success_response(LearningCenterOut.model_validate(center), "O'quv markazi yaratildi.")


@router.patch(
    "/{center_id}",
    summary="Update a learning center",
    description="Updates any field including status. Requires Admin or Super Admin.",
)
def update_learning_center(
    center_id: uuid.UUID,
    data: LearningCenterUpdateRequest,
    service: LearningCenterService = Depends(get_learning_center_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    center = service.update_center(center_id, data, actor_id=admin.id)
    return success_response(LearningCenterOut.model_validate(center), "O'quv markazi yangilandi.")


@router.delete(
    "/{center_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a learning center",
    description="Marks a learning center as deleted. Requires Admin or Super Admin.",
)
def delete_learning_center(
    center_id: uuid.UUID,
    service: LearningCenterService = Depends(get_learning_center_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    service.delete_center(center_id, actor_id=admin.id)
