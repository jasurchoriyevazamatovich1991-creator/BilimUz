"""
HTTP layer for the isolated Login API. Mounted at /auth/login-v2 (NOT
/auth/login) — the existing login endpoint in auth/router.py is untouched,
per this step's explicit scope. See registration/router.py for the same
pattern applied one step earlier.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.schemas import success_response
from app.db.session import get_db
from app.modules.auth.jwt.dependencies import get_jwt_service
from app.modules.auth.jwt.jwt_service import JWTService
from app.modules.auth.login.schemas import LoginRequest, LoginResponse
from app.modules.auth.login.service import LoginService
from app.modules.auth.repository import AuthRepository
from app.modules.auth.security.dependencies import get_password_service
from app.modules.auth.security.password_service import PasswordService

router = APIRouter(prefix="/auth/login-v2", tags=["Login"])


def get_login_service(
    db: Session = Depends(get_db),
    password_service: PasswordService = Depends(get_password_service),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> LoginService:
    return LoginService(AuthRepository(db), password_service, jwt_service)


@router.post("")
def login(
    data: LoginRequest,
    request: Request,
    service: LoginService = Depends(get_login_service),
):
    response: LoginResponse = service.login(
        data.email, data.password,
        ip=request.client.host if request.client else None,
        device=request.headers.get("user-agent"),
    )
    return success_response(response, "Tizimga muvaffaqiyatli kirdingiz.")
