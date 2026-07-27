"""
HTTP layer for the isolated Refresh Token API. Mounted at
/auth/refresh-v2 (NOT /auth/refresh) — the existing refresh endpoint in
auth/router.py is untouched, same pattern as registration/login.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.schemas import success_response
from app.db.session import get_db
from app.modules.auth.jwt.dependencies import get_jwt_service
from app.modules.auth.jwt.jwt_service import JWTService
from app.modules.auth.refresh.schemas import RefreshTokenRequest, RefreshTokenResponse
from app.modules.auth.refresh.service import RefreshService
from app.modules.auth.repository import AuthRepository

router = APIRouter(prefix="/auth/refresh-v2", tags=["Token Refresh"])


def get_refresh_service(
    db: Session = Depends(get_db),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> RefreshService:
    return RefreshService(AuthRepository(db), jwt_service)


@router.post("")
def refresh_token(
    data: RefreshTokenRequest,
    service: RefreshService = Depends(get_refresh_service),
):
    response: RefreshTokenResponse = service.refresh(data.refresh_token)
    return success_response(response, "Token yangilandi.")
