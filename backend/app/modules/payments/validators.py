"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.payments.constants import (
    ALLOWED_CURRENCIES,
    ALLOWED_PROVIDERS,
    MAX_PLAN_NAME_LENGTH,
    MIN_AMOUNT,
    MIN_DURATION_DAYS,
    MIN_PLAN_NAME_LENGTH,
)


def validate_amount(amount: float) -> float:
    if amount < MIN_AMOUNT:
        raise ValueError(f"Summa {MIN_AMOUNT} dan katta bo'lishi kerak")
    return amount


def validate_currency(currency: str) -> str:
    if currency not in ALLOWED_CURRENCIES:
        raise ValueError(f"Valyuta quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_CURRENCIES)}")
    return currency


def validate_provider(provider: str) -> str:
    if provider not in ALLOWED_PROVIDERS:
        raise ValueError(f"Provayder quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_PROVIDERS)}")
    return provider


def validate_plan_name(name: str) -> str:
    stripped = name.strip()
    if not (MIN_PLAN_NAME_LENGTH <= len(stripped) <= MAX_PLAN_NAME_LENGTH):
        raise ValueError(f"Reja nomi {MIN_PLAN_NAME_LENGTH}-{MAX_PLAN_NAME_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_duration_days(days: int) -> int:
    if days < MIN_DURATION_DAYS:
        raise ValueError(f"Davomiylik kamida {MIN_DURATION_DAYS} kun bo'lishi kerak")
    return days
