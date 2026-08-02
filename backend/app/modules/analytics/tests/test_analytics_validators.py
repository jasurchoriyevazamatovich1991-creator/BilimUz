"""Unit tests for pure date-range validation — no DB, no mocks."""
from datetime import date

import pytest

from app.modules.analytics.validators import validate_date_range


def test_valid_range_passes():
    validate_date_range(date(2026, 1, 1), date(2026, 1, 31))  # no exception


def test_start_after_end_rejected():
    with pytest.raises(ValueError):
        validate_date_range(date(2026, 2, 1), date(2026, 1, 1))


def test_range_over_max_days_rejected():
    with pytest.raises(ValueError):
        validate_date_range(date(2020, 1, 1), date(2026, 1, 1))


def test_same_day_range_is_valid():
    validate_date_range(date(2026, 1, 1), date(2026, 1, 1))  # no exception
