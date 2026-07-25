"""
HTTP layer for /api/v1/auth/*. Thin by design: parses the request,
delegates to AuthService, wraps the result in the standard envelope.
No business logic lives here. Brute-forceable endpoints (register, login,
verify) carry a Redis-backed rate limit per Security Engineer policy.
"""
from fastapi import APIRouter, Depends, Request, status

from app.modules.auth.constants import LOGIN_RATE_LIMIT, REGISTER_RATE_LIMIT, VERIFY_RATE_LIMIT
from app.modules.auth.dependencies import get_auth_repository, get_current_user
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
    UserPublic,
    VerifyRequest,
)
from app.modules.auth.service import AuthService
from app.core.middleware.rate_limit import rate_limit
from app.core.schemas import success_response
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_auth_service(repo: AuthRepository = Depends(get_auth_repository)) -> AuthService:
    return AuthService(repo)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register", *REGISTER_RATE_LIMIT))],
)
def register(data: RegisterRequest, service: AuthService = Depends(get_auth_service)):
    user, plain_code = service.register(data)
    # TODO(notifications module): send `plain_code` via SMS provider instead of returning it.
    return success_response(
        {"user_id": str(user.id), "debug_code": plain_code}, "Ro'yxatdan o'tish muvaffaqiyatli. Tasdiqlash kodi yuborildi."
    )


@router.post("/verify", dependencies=[Depends(rate_limit("verify", *VERIFY_RATE_LIMIT))])
def verify(data: VerifyRequest, service: AuthService = Depends(get_auth_service)):
    user = service.verify(data.user_id, data.code)
    return success_response(UserPublic.model_validate(user), "Akkaunt tasdiqlandi.")


@router.post("/login", dependencies=[Depends(rate_limit("login", *LOGIN_RATE_LIMIT))])
def login(data: LoginRequest, request: Request, service: AuthService = Depends(get_auth_service)):
    tokens: TokenPairResponse = service.login(
        data.identifier, data.password, request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    return success_response(tokens, "Tizimga muvaffaqiyatli kirdingiz.")


@router.post("/refresh")
def refresh(data: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    tokens = service.refresh(data.refresh_token)
    return success_response(tokens, "Token yangilandi.")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    service.logout(data.refresh_token)


@router.post("/logout-all")
def logout_all(
    service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user),
):
    count = service.logout_all_devices(current_user.id)
    return success_response({"devices_revoked": count}, "Barcha qurilmalardan chiqildi.")


@router.get("/sessions")
def sessions(
    service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user),
):
    return success_response(service.list_sessions(current_user.id), "Faol sessiyalar.")


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user),
):
    service.change_password(current_user.id, data.current_password, data.new_password)
    return success_response(None, "Parol o'zgartirildi. Barcha qurilmalardan chiqildi, qayta kiring.")


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return success_response(UserPublic.model_validate(current_user), "Foydalanuvchi ma'lumoti.")
