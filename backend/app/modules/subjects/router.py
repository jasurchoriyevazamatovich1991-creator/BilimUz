"""
HTTP layer for /api/v1/subjects/*. List/get are public (any prospective
student can browse subjects before registering); write operations require
Admin or Super Admin, enforced via the shared auth.require_roles dependency.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.modules.auth.dependencies import require_roles
from app.core.schemas import success_response
from app.modules.subjects.dependencies import get_subject_service
from app.modules.subjects.schemas import (
    SubjectCreateRequest,
    SubjectListParams,
    SubjectOut,
    SubjectUpdateRequest,
)
from app.modules.subjects.service import SubjectService
from app.modules.users.models import User

router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.get("")
def list_subjects(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="-created_at"),
    service: SubjectService = Depends(get_subject_service),
):
    params = SubjectListParams(page=page, per_page=per_page, search=search, status=status_filter, sort=sort)
    items, total = service.list_subjects(params)
    data = {
        "items": [SubjectOut.model_validate(i) for i in items],
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
    }
    return success_response(data, "Fanlar ro'yxati.")


@router.get("/{subject_id}")
def get_subject(subject_id: uuid.UUID, service: SubjectService = Depends(get_subject_service)):
    subject = service.get_subject(subject_id)
    return success_response(SubjectOut.model_validate(subject), "Fan topildi.")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_subject(
    data: SubjectCreateRequest,
    service: SubjectService = Depends(get_subject_service),
    current_user: User = Depends(require_roles("Admin", "Super Admin")),
):
    subject = service.create_subject(data, actor_id=current_user.id)
    return success_response(SubjectOut.model_validate(subject), "Fan yaratildi.")


@router.patch("/{subject_id}")
def update_subject(
    subject_id: uuid.UUID,
    data: SubjectUpdateRequest,
    service: SubjectService = Depends(get_subject_service),
    current_user: User = Depends(require_roles("Admin", "Super Admin")),
):
    subject = service.update_subject(subject_id, data, actor_id=current_user.id)
    return success_response(SubjectOut.model_validate(subject), "Fan yangilandi.")


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: uuid.UUID,
    service: SubjectService = Depends(get_subject_service),
    current_user: User = Depends(require_roles("Admin", "Super Admin")),
):
    service.delete_subject(subject_id, actor_id=current_user.id)
