"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.ai.constants import MAX_MESSAGE_LENGTH


def validate_message_content(content: str) -> str:
    stripped = content.strip()
    if not stripped:
        raise ValueError("Xabar bo'sh bo'lishi mumkin emas")
    if len(stripped) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Xabar {MAX_MESSAGE_LENGTH} belgidan oshmasligi kerak")
    return stripped


def validate_study_plan_dates(start_date, end_date) -> None:
    if start_date > end_date:
        raise ValueError("Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas")
