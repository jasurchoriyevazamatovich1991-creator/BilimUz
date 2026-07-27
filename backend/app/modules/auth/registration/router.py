"""
HTTP layer for the isolated Register API. Mounted at /auth/registration
(NOT /auth/register) — deliberately a different path from the existing
register endpoint in auth/router.py, so this can be built, tested, and
reviewed without touching or colliding with the existing route, login,
or any other existing auth endpoint. Cutover (replacing the old endpoint
with this one) is a separate, explicit future decision — see README.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.schemas import success_response
from app.db.session import get_db
from app.modules.auth.jwt.dependencies import get_jwt_service
from app.modules.auth.jwt.jwt_service import JWTService
from app.modules.auth.registration.schemas import RegistrationRequest, RegistrationResponse, RegisteredUserOut
from app.modules.auth.registration.service import RegistrationService
from app.modules.auth.repository import AuthRepository
from app.modules.auth.security.dependencies import get_password_service
from app.modules.auth.security.password_service import PasswordService

router = APIRouter(prefix="/auth/registration", tags=["Registration"])


def get_registration_service(
    db: Session = Depends(get_db),
    password_service: PasswordService = Depends(get_password_service),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> RegistrationService:
    return RegistrationService(AuthRepository(db), password_service, jwt_service)


@router.post("", status_code=status.HTTP_201_CREATED)
def register(
    data: RegistrationRequest,
    service: RegistrationService = Depends(get_registration_service),
):
    user, tokens = service.register(data)
    response = RegistrationResponse(user=RegisteredUserOut.model_validate(user), tokens=tokens)
    return success_response(response, "Ro'yxatdan o'tish muvaffaqiyatli.")
