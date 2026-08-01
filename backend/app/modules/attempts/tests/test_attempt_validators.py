"""Unit tests for pure timer/randomization functions — no DB, no mocks."""
import uuid
from datetime import datetime, timedelta, timezone

from app.modules.attempts.validators import build_question_order, compute_expiry, is_expired


def test_compute_expiry_adds_duration_minutes():
    start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert compute_expiry(start, 60) == datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)


def test_is_expired_false_before_deadline():
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert is_expired(future) is False


def test_is_expired_true_after_deadline():
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert is_expired(past) is True


def test_is_expired_false_when_none():
    assert is_expired(None) is False


def test_build_question_order_preserves_all_ids():
    ids = [uuid.uuid4() for _ in range(10)]
    ordered = build_question_order(ids, shuffle=True)
    assert set(ordered) == set(ids)
    assert len(ordered) == len(ids)


def test_build_question_order_no_shuffle_preserves_input_order():
    ids = [uuid.uuid4() for _ in range(5)]
    assert build_question_order(ids, shuffle=False) == ids
