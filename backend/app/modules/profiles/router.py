"""
HTTP layer for /api/v1/profiles/*. Own profile: any authenticated user
(Teacher, Student, Admin, Super Admin — everyone can see/edit their own).
Other users' profiles: Super Admin only — since School Admin/Learning
Center Admin roles were explicitly NOT introduced this sprint (approved
decision), there is no school-scoped or center-scoped visibility tier;
the only role that can view/manage another user's profile is Super Admin.
"""
import uuid

from fastapi import APIRouter, Depends, Query

from app.core.schemas import success_response
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.profiles.dependencies import get_profile_service
from app.modules.profiles.schemas import ProfileListParams, ProfileUpdateRequest
from app.modules.profiles.service import ProfileService
from app.modules.users.models import User

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.get(
    "/me",
    summary="Get my own profile",
    description="Returns a composed view of User (name, phone, gender, birth_date, image) and "
                "Profile (bio, address, socials, school_id, learning_center_id) fields. "
                "Auto-creates an empty Profile row on first access if one doesn't exist yet.",
)
def get_my_profile(
    service: ProfileService = Depends(get_profile_service),
    user: User = Depends(get_current_user),
):
    profile = service.get_profile(user.id)
    return success_response(profile, "Mening profilim.")


@router.patch(
    "/me",
    summary="Update my own profile",
    description="Updates only Profile-owned fields (bio, address, telegram, instagram, website, "
                "school_id, learning_center_id). first_name/last_name/phone/gender/birth_date are NOT "
                "editable here — they belong to the users module. 422 if school_id or learning_center_id "
                "don't reference existing rows.",
)
def update_my_profile(
    data: ProfileUpdateRequest,
    service: ProfileService = Depends(get_profile_service),
    user: User = Depends(get_current_user),
):
    profile = service.update_profile(user.id, data, actor_id=user.id)
    return success_response(profile, "Profilim yangilandi.")


@router.get(
    "",
    summary="List profiles",
    description="Filterable by school_id/learning_center_id, paginated. Super Admin only.",
)
def list_profiles(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    school_id: uuid.UUID | None = Query(default=None),
    learning_center_id: uuid.UUID | None = Query(default=None),
    service: ProfileService = Depends(get_profile_service),
    _admin: User = Depends(require_roles("Super Admin")),
):
    params = ProfileListParams(page=page, per_page=per_page, school_id=school_id, learning_center_id=learning_center_id)
    items, total = service.list_profiles(params)
    data = {
        "items": items,
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Profillar ro'yxati.")


@router.get(
    "/{user_id}",
    summary="Get another user's profile",
    description="Super Admin only.",
)
def get_profile(
    user_id: uuid.UUID,
    service: ProfileService = Depends(get_profile_service),
    _admin: User = Depends(require_roles("Super Admin")),
):
    profile = service.get_profile(user_id)
    return success_response(profile, "Profil.")


@router.patch(
    "/{user_id}",
    summary="Update another user's profile",
    description="Super Admin only. Same field restrictions as PATCH /me.",
)
def update_profile(
    user_id: uuid.UUID,
    data: ProfileUpdateRequest,
    service: ProfileService = Depends(get_profile_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    profile = service.update_profile(user_id, data, actor_id=admin.id)
    return success_response(profile, "Profil yangilandi.")
