"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.results.constants import ALLOWED_PERIODS


def validate_ranking_period(period: str) -> str:
    if period not in ALLOWED_PERIODS:
        raise ValueError(f"period quyidagilardan biri bo'lishi kerak: {', '.join(ALLOWED_PERIODS)}")
    return period
