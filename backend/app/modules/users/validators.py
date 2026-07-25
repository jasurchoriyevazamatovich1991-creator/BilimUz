"""Pure validation functions — no I/O, reusable from schemas or services."""
from datetime import date

from app.modules.users.constants import MAX_NAME_LENGTH, MIN_NAME_LENGTH


def validate_person_name(name: str) -> str:
    stripped = name.strip()
    if not (MIN_NAME_LENGTH <= len(stripped) <= MAX_NAME_LENGTH):
        raise ValueError(f"Ism {MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_birth_date(birth_date: date | None) -> date | None:
    if birth_date is None:
        return None
    if birth_date >= date.today():
        raise ValueError("Tug'ilgan sana kelajakda bo'lishi mumkin emas")
    age_years = (date.today() - birth_date).days / 365.25
    if age_years > 120:
        raise ValueError("Tug'ilgan sana noto'g'ri ko'rinadi")
    return birth_date
