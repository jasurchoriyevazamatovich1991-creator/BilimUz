"""Pure validation functions — no I/O, reusable from schemas or services."""
from datetime import date

from app.modules.analytics.constants import MAX_DATE_RANGE_DAYS


def validate_date_range(start: date, end: date) -> None:
    if start > end:
        raise ValueError("Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas")
    if (end - start).days > MAX_DATE_RANGE_DAYS:
        raise ValueError(f"Sana oralig'i {MAX_DATE_RANGE_DAYS} kundan oshmasligi kerak")
