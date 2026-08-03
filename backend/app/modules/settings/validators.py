"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.settings.constants import MAX_KEY_LENGTH, MAX_PORT, MIN_KEY_LENGTH, MIN_PORT, MIN_SECRET_LENGTH


def validate_setting_key(key: str) -> str:
    stripped = key.strip()
    if not (MIN_KEY_LENGTH <= len(stripped) <= MAX_KEY_LENGTH):
        raise ValueError(f"Sozlama kaliti {MIN_KEY_LENGTH}-{MAX_KEY_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_port(port: int) -> int:
    if not (MIN_PORT <= port <= MAX_PORT):
        raise ValueError(f"Port {MIN_PORT}-{MAX_PORT} oralig'ida bo'lishi kerak")
    return port


def validate_secret_value(value: str) -> str:
    if len(value) < MIN_SECRET_LENGTH:
        raise ValueError("Maxfiy qiymat bo'sh bo'lishi mumkin emas")
    return value
