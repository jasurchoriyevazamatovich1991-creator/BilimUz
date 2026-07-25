"""
Data-access layer. Only SQLAlchemy here — no business rules, no password
hashing, no token creation. Service calls these methods and decides what
they mean.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.constants import PASSWORD_HISTORY_SIZE
from app.modules.auth.models import LoginHistory, PasswordHistory, RefreshToken, VerificationCode
from app.modules.users.models import User


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_identifier(self, identifier: str) -> User | None:
        stmt = select(User).where(
            (User.email == identifier) | (User.phone == identifier),
            User.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def create_user(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def create_verification_code(self, code: VerificationCode) -> VerificationCode:
        self.db.add(code)
        self.db.flush()
        return code

    def get_active_verification_code(self, user_id: uuid.UUID) -> VerificationCode | None:
        stmt = (
            select(VerificationCode)
            .where(VerificationCode.user_id == user_id, VerificationCode.status == "pending")
            .order_by(VerificationCode.created_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def create_refresh_token(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        self.db.flush()
        return token

    def get_refresh_token_by_jti(self, jti: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.jti == jti, RefreshToken.status == "active")
        return self.db.execute(stmt).scalar_one_or_none()

    def revoke_refresh_token(self, token: RefreshToken) -> None:
        token.status = "revoked"
        self.db.flush()

    def list_active_sessions(self, user_id: uuid.UUID) -> list[RefreshToken]:
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.status == "active"
        ).order_by(RefreshToken.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def revoke_all_refresh_tokens(self, user_id: uuid.UUID, except_jti: str | None = None) -> int:
        """Used by 'logout all devices' and forced-logout-on-password-change.
        Returns how many tokens were revoked (useful for the audit log)."""
        tokens = self.list_active_sessions(user_id)
        count = 0
        for token in tokens:
            if token.jti != except_jti:
                token.status = "revoked"
                count += 1
        self.db.flush()
        return count

    def record_login(self, entry: LoginHistory) -> None:
        self.db.add(entry)
        self.db.flush()

    def activate_user(self, user: User) -> None:
        from app.modules.users.models import UserStatus
        user.status = UserStatus.ACTIVE
        user.updated_at = datetime.now(timezone.utc)
        self.db.flush()

    def get_recent_password_hashes(self, user_id: uuid.UUID) -> list[str]:
        stmt = (
            select(PasswordHistory.password_hash)
            .where(PasswordHistory.user_id == user_id)
            .order_by(PasswordHistory.created_at.desc())
            .limit(PASSWORD_HISTORY_SIZE)
        )
        return list(self.db.execute(stmt).scalars().all())

    def add_password_history(self, user_id: uuid.UUID, password_hash: str) -> None:
        self.db.add(PasswordHistory(user_id=user_id, password_hash=password_hash))
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
