"""Pure validation functions — no I/O, reusable from schemas or services."""
from datetime import date

from app.modules.system_logs.constants import ALLOWED_LEVELS, MAX_DATE_RANGE_DAYS, MAX_MESSAGE_LENGTH, MAX_SOURCE_LENGTH


def validate_level(level: str) -> str:
    if level not in ALLOWED_LEVELS:
        raise ValueError(f"level quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_LEVELS)}")
    return level


def validate_message(message: str) -> str:
    stripped = message.strip()
    if not stripped:
        raise ValueError("Xabar bo'sh bo'lishi mumkin emas")
    if len(stripped) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Xabar {MAX_MESSAGE_LENGTH} belgidan oshmasligi kerak")
    return stripped


def validate_source(source: str | None) -> str | None:
    if source is None:
        return None
    stripped = source.strip()
    if len(stripped) > MAX_SOURCE_LENGTH:
        raise ValueError(f"Manba nomi {MAX_SOURCE_LENGTH} belgidan oshmasligi kerak")
    return stripped


def validate_date_range(start: date | None, end: date | None) -> None:
    if start is None or end is None:
        return
    if start > end:
        raise ValueError("Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas")
    if (end - start).days > MAX_DATE_RANGE_DAYS:
        raise ValueError(f"Sana oralig'i {MAX_DATE_RANGE_DAYS} kundan oshmasligi kerak")
