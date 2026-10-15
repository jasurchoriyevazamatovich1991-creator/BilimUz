"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.catalog.constants import MAX_NAME_LENGTH, MIN_NAME_LENGTH


def validate_product_name(name: str) -> str:
    stripped = name.strip()
    if not (MIN_NAME_LENGTH <= len(stripped) <= MAX_NAME_LENGTH):
        raise ValueError(f"Mahsulot nomi {MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_price(price: float) -> float:
    if price < 0:
        raise ValueError("Narx manfiy bo'lishi mumkin emas")
    return price


def validate_duration_days(duration_days: int | None) -> int | None:
    """None is valid and means 'no expiry' (e.g. a one-time, lifetime
    mock-test unlock) — NOT a missing/unset value. Zero or negative is
    never valid."""
    if duration_days is not None and duration_days <= 0:
        raise ValueError("Amal qilish muddati (kun) musbat son bo'lishi kerak, yoki umuman ko'rsatilmasligi mumkin")
    return duration_days
