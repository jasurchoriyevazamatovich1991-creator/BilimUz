"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.topics.constants import MAX_TITLE_LENGTH, MIN_TITLE_LENGTH


def validate_topic_title(title: str) -> str:
    stripped = title.strip()
    if not (MIN_TITLE_LENGTH <= len(stripped) <= MAX_TITLE_LENGTH):
        raise ValueError(f"Mavzu sarlavhasi {MIN_TITLE_LENGTH}-{MAX_TITLE_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_order_number(order_number: int) -> int:
    if order_number < 0:
        raise ValueError("order_number manfiy bo'lishi mumkin emas")
    return order_number
