"""
Pure validation functions — no I/O, no DB, no HTTP. Called from Pydantic
schemas (field_validator) and reusable anywhere else (e.g. AI module input).
"""
import re

from app.modules.auth.constants import COMMON_WEAK_PASSWORDS, PASSWORD_MIN_LENGTH

_UZ_PHONE_RE = re.compile(r"^\+998\d{9}$")
_UPPER_RE = re.compile(r"[A-Z]")
_LOWER_RE = re.compile(r"[a-z]")
_DIGIT_RE = re.compile(r"\d")
_SPECIAL_RE = re.compile(r"[!@#$%^&*()\-_=+\[\]{};:,.<>/?]")


def validate_uzbek_phone(phone: str) -> str:
    if not _UZ_PHONE_RE.match(phone):
        raise ValueError("Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak")
    return phone


def validate_password_strength(password: str) -> str:
    """Security Engineer policy: 12+ chars, upper, lower, digit, special char."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Parol kamida {PASSWORD_MIN_LENGTH} belgidan iborat bo'lishi kerak")
    if not _UPPER_RE.search(password):
        raise ValueError("Parolda kamida bitta katta harf bo'lishi kerak")
    if not _LOWER_RE.search(password):
        raise ValueError("Parolda kamida bitta kichik harf bo'lishi kerak")
    if not _DIGIT_RE.search(password):
        raise ValueError("Parolda kamida bitta raqam bo'lishi kerak")
    if not _SPECIAL_RE.search(password):
        raise ValueError("Parolda kamida bitta maxsus belgi bo'lishi kerak (!@#$%...)")
    if password.lower() in COMMON_WEAK_PASSWORDS:
        raise ValueError("Bu parol juda ko'p tarqalgan, boshqasini tanlang")
    return password


def validate_verification_code_format(code: str) -> bool:
    return code.isdigit() and len(code) == 6
