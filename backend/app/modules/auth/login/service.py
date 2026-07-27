"""
Business logic for the isolated Login API. Authenticates by email only
(per this step's explicit requirement), verifying with the NEW
PasswordService (Argon2) — which means, by design, this endpoint can
only authenticate users whose password was hashed by the NEW Registration
API (Step 3). Users created via the existing /auth/register (bcrypt) will
get InvalidCredentialsException here, same as a wrong password — see
README "Known limitation" for why that's the correct, secure behavior
(never reveal *why* auth failed) rather than a bug to silently patch.
"""
from passlib.exc import UnknownHashError

from app.core.audit import log_action
from app.core.exceptions import InvalidCredentialsException
from app.core.security import hash_refresh_token
from app.modules.auth.jwt.jwt_service import JWTService
from app.modules.auth.login.schemas import LoginResponse
from app.modules.auth.models import LoginHistory, RefreshToken
from app.modules.auth.repository import AuthRepository
from app.modules.auth.security.password_service import PasswordService


class LoginService:
    def __init__(self, repository: AuthRepository, password_service: PasswordService, jwt_service: JWTService):
        self.repo = repository
        self.password_service = password_service
        self.jwt_service = jwt_service

    def login(self, email: str, password: str, ip: str | None, device: str | None) -> LoginResponse:
        user = self.repo.get_user_by_identifier(email)
        if user is None or not self._verify(password, user.password_hash):
            raise InvalidCredentialsException("Login yoki parol noto'g'ri")

        response = self._issue_tokens(user.id)
        self.repo.record_login(LoginHistory(user_id=user.id, ip_address=ip, device=device))
        log_action(self.repo.db, action="auth.login_success", user_id=user.id, ip_address=ip)
        self.repo.commit()
        return response

    def _verify(self, plain_password: str, password_hash: str) -> bool:
        try:
            return self.password_service.verify_password(plain_password, password_hash)
        except UnknownHashError:
            # Hash was produced by a different scheme (e.g. the existing
            # bcrypt system) — treat exactly like a wrong password. Never
            # leak "which hashing scheme this account uses" to the caller.
            return False

    def _issue_tokens(self, user_id) -> LoginResponse:
        access = self.jwt_service.create_access_token(subject=str(user_id))
        refresh = self.jwt_service.create_refresh_token(subject=str(user_id))
        access_payload = self.jwt_service.decode_token(access)
        refresh_payload = self.jwt_service.decode_token(refresh)

        self.repo.create_refresh_token(
            RefreshToken(user_id=user_id, token_hash=hash_refresh_token(refresh), jti=refresh_payload.jti)
        )

        return LoginResponse(
            access_token=access,
            refresh_token=refresh,
            access_token_expires_in=int((access_payload.exp - access_payload.iat).total_seconds()),
            access_token_expires_at=access_payload.exp,
            refresh_token_expires_in=int((refresh_payload.exp - refresh_payload.iat).total_seconds()),
            refresh_token_expires_at=refresh_payload.exp,
        )
