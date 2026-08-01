"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.tests.constants import (
    ALLOWED_STATUS_TRANSITIONS,
    MAX_DURATION_MINUTES,
    MAX_PASSING_SCORE,
    MAX_TITLE_LENGTH,
    MIN_DURATION_MINUTES,
    MIN_PASSING_SCORE,
    MIN_TITLE_LENGTH,
)


def validate_test_title(title: str) -> str:
    stripped = title.strip()
    if not (MIN_TITLE_LENGTH <= len(stripped) <= MAX_TITLE_LENGTH):
        raise ValueError(f"Sarlavha {MIN_TITLE_LENGTH}-{MAX_TITLE_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_duration(duration: int) -> int:
    if not (MIN_DURATION_MINUTES <= duration <= MAX_DURATION_MINUTES):
        raise ValueError(f"Davomiylik {MIN_DURATION_MINUTES}-{MAX_DURATION_MINUTES} daqiqa oralig'ida bo'lishi kerak")
    return duration


def validate_passing_score(score: float | None) -> float | None:
    if score is None:
        return None
    if not (MIN_PASSING_SCORE <= score <= MAX_PASSING_SCORE):
        raise ValueError(f"O'tish balli {MIN_PASSING_SCORE}-{MAX_PASSING_SCORE}% oralig'ida bo'lishi kerak")
    return score


def is_valid_status_transition(current: str, new: str) -> bool:
    return new in ALLOWED_STATUS_TRANSITIONS.get(current, set())
