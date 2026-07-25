"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.permissions.constants import (
    CODE_PATTERN,
    KNOWN_MODULES,
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
)


def validate_permission_name(name: str) -> str:
    stripped = name.strip()
    if not (MIN_NAME_LENGTH <= len(stripped) <= MAX_NAME_LENGTH):
        raise ValueError(f"Nom {MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_permission_code(code: str) -> str:
    upper = code.strip().upper()
    if not CODE_PATTERN.match(upper):
        raise ValueError("Kod SCREAMING_SNAKE_CASE formatida bo'lishi kerak (masalan CREATE_TEST)")
    return upper


def validate_module_name(module: str) -> str:
    lower = module.strip().lower()
    if lower not in KNOWN_MODULES:
        raise ValueError(f"module quyidagilardan biri bo'lishi kerak: {', '.join(KNOWN_MODULES)}")
    return lower
