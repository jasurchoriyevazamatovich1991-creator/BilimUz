"""
Business logic for the isolated Register API. Reuses the EXISTING
AuthRepository (unmodified) for duplicate checks and user creation —
those methods already do exactly what's needed, so no repository changes
were required, per this step's "repository methods if required" clause.

Uses the NEW PasswordService (Argon2, structured errors) and NEW
JWTService (typed payloads, nbf claim) built in Steps 1-2 — this is the
first place either one is actually wired into a runnable endpoint.
"""
import uuid

from app.core.exceptions import UserAlreadyExistsException
from app.core.security import hash_refresh_token
from app.modules.auth.exceptions import WeakPasswordException
from app.modules.auth.jwt.jwt_service import JWTService
from app.modules.auth.jwt.schemas import TokenPair
from app.modules.auth.models import RefreshToken
from app.modules.auth.repository import AuthRepository
from app.modules.auth.registration.schemas import RegistrationRequest
from app.modules.auth.security.password_service import PasswordService
from app.modules.auth.service import DEFAULT_STUDENT_ROLE_ID
from app.modules.users.models import User


class RegistrationService:
    def __init__(self, repository: AuthRepository, password_service: PasswordService, jwt_service: JWTService):
        self.repo = repository
        self.password_service = password_service
        self.jwt_service = jwt_service

    def register(self, data: RegistrationRequest) -> tuple[User, TokenPair]:
        self._reject_if_duplicate(data.phone, data.email)

        validation = self.password_service.validate_password_strength(data.password)
        if not validation.is_valid:
            raise WeakPasswordException(
                "Parol talablarga javob bermaydi",
                errors=[e.message for e in validation.errors],
            )

        user = User(
            role_id=DEFAULT_STUDENT_ROLE_ID,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            email=data.email,
            password_hash=self.password_service.hash_password(data.password),
        )
        self.repo.create_user(user)

        tokens = self._issue_tokens(user.id)
        self.repo.commit()
        return user, tokens

    def _reject_if_duplicate(self, phone: str, email: str | None) -> None:
        if self.repo.get_user_by_identifier(phone):
            raise UserAlreadyExistsException("Bu telefon raqami allaqachon ro'yxatdan o'tgan")
        if email and self.repo.get_user_by_identifier(email):
            raise UserAlreadyExistsException("Bu email allaqachon ro'yxatdan o'tgan")

    def _issue_tokens(self, user_id: uuid.UUID) -> TokenPair:
        access = self.jwt_service.create_access_token(subject=str(user_id))
        refresh = self.jwt_service.create_refresh_token(subject=str(user_id))
        payload = self.jwt_service.decode_token(refresh)

        self.repo.create_refresh_token(
            RefreshToken(
                user_id=user_id,
                token_hash=hash_refresh_token(refresh),
                jti=payload.jti,
            )
        )
        return TokenPair(access_token=access, refresh_token=refresh)
