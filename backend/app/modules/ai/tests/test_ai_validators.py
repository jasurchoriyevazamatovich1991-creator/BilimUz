"""Unit tests for pure validation functions — no I/O."""
from datetime import date

import pytest

from app.modules.ai.validators import validate_message_content, validate_study_plan_dates


def test_valid_message_passes():
    assert validate_message_content("  Salom!  ") == "Salom!"


def test_empty_message_rejected():
    with pytest.raises(ValueError):
        validate_message_content("   ")


def test_message_over_max_length_rejected():
    with pytest.raises(ValueError):
        validate_message_content("x" * 4001)


def test_message_at_exact_max_length_passes():
    validate_message_content("x" * 4000)  # no exception


def test_valid_date_range_passes():
    validate_study_plan_dates(date(2026, 1, 1), date(2026, 6, 1))  # no exception


def test_invalid_date_range_rejected():
    with pytest.raises(ValueError):
        validate_study_plan_dates(date(2026, 6, 1), date(2026, 1, 1))
