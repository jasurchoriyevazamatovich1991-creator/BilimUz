"""Pure validation functions — no I/O. Reuses
app.modules.auth.validators.validate_uzbek_phone (a pure function import,
not a repository/service dependency — this does not count as a
cross-module coupling the way a repository read would, same reasoning
already stated in the architecture doc)."""
import re

from app.modules.auth.validators import validate_uzbek_phone
from app.modules.notifications.constants import ALLOWED_CHANNELS, MAX_TEMPLATE_CODE_LENGTH, MAX_TITLE_LENGTH

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_channel(channel: str) -> str:
    if channel not in ALLOWED_CHANNELS:
        raise ValueError(f"channel quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_CHANNELS)}")
    return channel


def validate_title(title: str) -> str:
    stripped = title.strip()
    if not (1 <= len(stripped) <= MAX_TITLE_LENGTH):
        raise ValueError(f"Sarlavha 1-{MAX_TITLE_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_email_address(email: str) -> str:
    if not _EMAIL_RE.match(email):
        raise ValueError("Email manzili noto'g'ri formatda")
    return email


def validate_phone_for_sms(phone: str) -> str:
    return validate_uzbek_phone(phone)


def validate_template_code(code: str) -> str:
    stripped = code.strip()
    if not (1 <= len(stripped) <= MAX_TEMPLATE_CODE_LENGTH):
        raise ValueError(f"Shablon kodi 1-{MAX_TEMPLATE_CODE_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped
