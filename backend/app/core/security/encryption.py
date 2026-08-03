"""
Symmetric encryption for secrets stored at rest (Sprint 8 — settings
module: smtp_settings.password, payment_settings.secret_key,
ai_settings.api_key). Uses Fernet (AES-128-CBC + HMAC, via the
`cryptography` library) — the standard, boring, correct choice, not a
custom scheme.

If FILE_ENCRYPTION_KEY is ever lost or rotated without a migration plan,
every previously-encrypted row becomes permanently unreadable — there is
no recovery path, by the nature of symmetric encryption. This is stated
here, not just in the architecture doc, because it's the single most
consequential operational fact about this file.
"""
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class EncryptionService:
    def __init__(self, key: str | None = None) -> None:
        settings = get_settings()
        self._fernet = Fernet((key or settings.FILE_ENCRYPTION_KEY).encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Shifrlangan qiymatni ochib bo'lmadi — kalit noto'g'ri yoki ma'lumot buzilgan") from exc
