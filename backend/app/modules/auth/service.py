"""
Business logic for authentication. Knows nothing about HTTP (no Request/
Response objects) — only domain exceptions, so it's reusable from a CLI,
a background job, or a future Telegram bot without modification.
"""
import uuid

import jwt

from app.modules.auth.exceptions import CurrentPasswordIncorrectException, PasswordReuseException
from app.modules.auth.models import LoginHistory, PasswordHistory, RefreshToken, VerificationCode
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import RegisterRequest, SessionOut, TokenPairResponse
from app.core.audit import log_action
from app.core.exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    UserAlreadyExistsException,
    UserNotFoundException,
    VerificationCodeInvalidException,
)
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_verification_code,
    hash_password,
    hash_refresh_token,
    hash_verification_code,
    verify_password,
    verify_verification_code,
)
from app.modules.users.models import User

DEFAULT_STUDENT_ROLE_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")  # seeded in DB


class AuthService:
    def __init__(self, repository: AuthRepository):
        self.repo = repository

    def register(self, data: RegisterRequest) -> tuple[User, str]:
        if self.repo.get_user_by_identifier(data.phone) or (
            data.email and self.repo.get_user_by_identifier(data.email)
        ):
            raise UserAlreadyExistsException("Bu telefon yoki email allaqachon ro'yxatdan o'tgan")

        user = User(
            role_id=DEFAULT_STUDENT_ROLE_ID,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            email=data.email,
            password_hash=hash_password(data.password),
        )
        self.repo.create_user(user)
        self.repo.add_password_history(user.id, user.password_hash)

        plain_code = generate_verification_code()
        code_row = VerificationCode(
            user_id=user.id,
            destination=data.phone,
            code_hash=hash_verification_code(plain_code),
            purpose="register",
        )
        self.repo.create_verification_code(code_row)
        log_action(self.repo.db, action="auth.register", user_id=user.id)
        self.repo.commit()
        return user, plain_code

    def verify(self, user_id: uuid.UUID, code: str) -> User:
        user = self._require_user(user_id)
        code_row = self.repo.get_active_verification_code(user_id)
        if code_row is None or code_row.attempts >= 5:
            raise VerificationCodeInvalidException("Kod eskirgan yoki urinishlar tugadi")
        if not verify_verification_code(code, code_row.code_hash):
            code_row.attempts += 1
            self.repo.commit()
            raise VerificationCodeInvalidException("Kod noto'g'ri")

        code_row.status = "used"
        self.repo.activate_user(user)
        log_action(self.repo.db, action="auth.verify", user_id=user.id)
        self.repo.commit()
        return user

    def login(self, identifier: str, password: str, ip: str | None, device: str | None) -> TokenPairResponse:
        user = self.repo.get_user_by_identifier(identifier)
        if user is None or not verify_password(password, user.password_hash):
            log_action(self.repo.db, action="auth.login_failed", ip_address=ip, metadata={"identifier": identifier})
            self.repo.commit()
            raise InvalidCredentialsException("Login yoki parol noto'g'ri")

        tokens = self._issue_token_pair(user.id, ip, device)
        self.repo.record_login(LoginHistory(user_id=user.id, ip_address=ip, device=device))
        log_action(self.repo.db, action="auth.login_success", user_id=user.id, ip_address=ip)
        self.repo.commit()
        return tokens

    def refresh(self, refresh_token: str) -> TokenPairResponse:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError:
            raise InvalidTokenException("Refresh token yaroqsiz")
        if payload.get("type") != TokenType.REFRESH.value:
            raise InvalidTokenException("Token turi noto'g'ri")

        stored = self.repo.get_refresh_token_by_jti(payload["jti"])
        if stored is None or stored.token_hash != hash_refresh_token(refresh_token):
            raise InvalidTokenException("Token bekor qilingan yoki topilmadi")

        self.repo.revoke_refresh_token(stored)  # rotation: old token is single-use
        tokens = self._issue_token_pair(uuid.UUID(payload["sub"]), stored.ip_address, stored.user_agent)
        self.repo.commit()
        return tokens

    def logout(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError:
            return  # already invalid — logout is idempotent
        stored = self.repo.get_refresh_token_by_jti(payload.get("jti", ""))
        if stored:
            self.repo.revoke_refresh_token(stored)
            log_action(self.repo.db, action="auth.logout", user_id=stored.user_id)
            self.repo.commit()

    def logout_all_devices(self, user_id: uuid.UUID) -> int:
        count = self.repo.revoke_all_refresh_tokens(user_id)
        log_action(self.repo.db, action="auth.logout_all", user_id=user_id, metadata={"devices_revoked": count})
        self.repo.commit()
        return count

    def list_sessions(self, user_id: uuid.UUID) -> list[SessionOut]:
        tokens = self.repo.list_active_sessions(user_id)
        return [
            SessionOut(id=t.id, device=t.user_agent, ip_address=t.ip_address, created_at=t.created_at)
            for t in tokens
        ]

    def change_password(self, user_id: uuid.UUID, current_password: str, new_password: str) -> None:
        user = self._require_user(user_id)
        if not verify_password(current_password, user.password_hash):
            raise CurrentPasswordIncorrectException("Joriy parol noto'g'ri")

        recent_hashes = self.repo.get_recent_password_hashes(user_id)
        if any(verify_password(new_password, h) for h in recent_hashes):
            raise PasswordReuseException("Bu parol yaqinda ishlatilgan, boshqasini tanlang")

        user.password_hash = hash_password(new_password)
        self.repo.add_password_history(user_id, user.password_hash)
        revoked = self.repo.revoke_all_refresh_tokens(user_id)  # force re-login everywhere
        log_action(self.repo.db, action="auth.password_changed", user_id=user_id, metadata={"devices_revoked": revoked})
        self.repo.commit()

    def _issue_token_pair(self, user_id: uuid.UUID, ip: str | None, device: str | None) -> TokenPairResponse:
        access = create_access_token(user_id)
        refresh = create_refresh_token(user_id)
        payload = decode_token(refresh)
        self.repo.create_refresh_token(
            RefreshToken(
                user_id=user_id,
                token_hash=hash_refresh_token(refresh),
                jti=payload["jti"],
                ip_address=ip,
                user_agent=device,
            )
        )
        return TokenPairResponse(access_token=access, refresh_token=refresh)

    def _require_user(self, user_id: uuid.UUID) -> User:
        user = self.repo.get_user_by_id(user_id)
        if user is None:
            raise UserNotFoundException("Foydalanuvchi topilmadi")
        return user
