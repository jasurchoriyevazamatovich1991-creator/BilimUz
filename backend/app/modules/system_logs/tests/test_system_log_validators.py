"""Unit tests for pure validation functions — no I/O."""
from datetime import date

import pytest

from app.modules.system_logs.constants import MAX_MESSAGE_LENGTH
from app.modules.system_logs.validators import validate_date_range, validate_level, validate_message, validate_source


@pytest.mark.parametrize("level", ["info", "warning", "error", "critical"])
def test_all_allowed_levels_pass(level):
    assert validate_level(level) == level


def test_invalid_level_rejected():
    with pytest.raises(ValueError):
        validate_level("debug")


def test_empty_message_rejected():
    with pytest.raises(ValueError):
        validate_message("   ")


def test_message_over_max_length_rejected():
    with pytest.raises(ValueError):
        validate_message("x" * (MAX_MESSAGE_LENGTH + 1))


def test_none_source_allowed():
    assert validate_source(None) is None


def test_date_range_over_90_days_rejected():
    with pytest.raises(ValueError):
        validate_date_range(date(2026, 1, 1), date(2026, 6, 1))


def test_date_range_within_90_days_passes():
    validate_date_range(date(2026, 1, 1), date(2026, 2, 1))  # no exception
