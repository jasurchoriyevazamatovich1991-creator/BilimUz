"""Pure functions — no I/O, no DB, reusable from the service layer.
Timer arithmetic and randomization live here specifically so they're
unit-testable without a database (see tests/test_attempt_validators.py)."""
import random
import uuid
from datetime import datetime, timedelta, timezone


def compute_expiry(start_time: datetime, duration_minutes: int) -> datetime:
    return start_time + timedelta(minutes=duration_minutes)


def is_expired(expires_at: datetime | None, now: datetime | None = None) -> bool:
    if expires_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now > expires_at


def build_question_order(question_ids: list[uuid.UUID], shuffle: bool) -> list[uuid.UUID]:
    """Called exactly once, at attempt start. The result is persisted
    (test_attempts.question_order) — this function is never called again
    for the same attempt, which is why a plain (non-seeded) shuffle is
    correct here: reproducibility comes from storage, not from re-deriving
    the same random sequence twice."""
    ordered = list(question_ids)
    if shuffle:
        random.shuffle(ordered)
    return ordered
