"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.roles.constants import MAX_NAME_LENGTH, MIN_NAME_LENGTH


def validate_role_name(name: str) -> str:
    stripped = name.strip()
    if not (MIN_NAME_LENGTH <= len(stripped) <= MAX_NAME_LENGTH):
        raise ValueError(f"Rol nomi {MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped
