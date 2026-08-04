"""Unit tests for pure date-range validation — no I/O."""
from datetime import date

import pytest

from app.modules.audit_logs.validators import validate_date_range


def test_valid_range_passes():
    validate_date_range(date(2026, 1, 1), date(2026, 3, 1))  # no exception


def test_none_dates_allowed():
    validate_date_range(None, None)  # no exception — filtering is optional


def test_start_after_end_rejected():
    with pytest.raises(ValueError):
        validate_date_range(date(2026, 3, 1), date(2026, 1, 1))


def test_range_over_90_days_rejected():
    with pytest.raises(ValueError):
        validate_date_range(date(2026, 1, 1), date(2026, 6, 1))


def test_range_at_exactly_90_days_passes():
    validate_date_range(date(2026, 1, 1), date(2026, 4, 1))  # exactly 90 days


def test_range_at_91_days_rejected():
    with pytest.raises(ValueError):
        validate_date_range(date(2026, 1, 1), date(2026, 4, 2))  # 91 days, one over
