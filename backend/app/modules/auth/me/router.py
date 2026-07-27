"""
HTTP layer for the isolated GET /me endpoint. Mounted at /auth/me-v2
(NOT /auth/me) — the existing endpoint in auth/router.py is untouched.
"""
from fastapi import APIRouter, Depends

from app.core.schemas import success_response
from app.modules.auth.me.dependencies import get_current_user_v2, get_me_service
from app.modules.auth.me.schemas import MeResponse
from app.modules.auth.me.service import MeService
from app.modules.users.models import User

router = APIRouter(prefix="/auth/me-v2", tags=["Profile"])


@router.get("")
def get_me(
    current_user: User = Depends(get_current_user_v2),
    service: MeService = Depends(get_me_service),
):
    profile: MeResponse = service.get_profile(current_user)
    return success_response(profile, "Foydalanuvchi profili.")
