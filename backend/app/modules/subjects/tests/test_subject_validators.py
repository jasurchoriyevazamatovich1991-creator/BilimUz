"""
Validator edge cases — boundary values, empty input, large input, special
characters. Per QA policy: every validator gets boundary + invalid + valid
coverage, not just the happy path.
"""
import pytest

from app.modules.subjects.constants import MAX_NAME_LENGTH, MIN_NAME_LENGTH
from app.modules.subjects.validators import validate_hex_color, validate_subject_name


def test_name_at_minimum_boundary_is_valid():
    assert validate_subject_name("A" * MIN_NAME_LENGTH) == "A" * MIN_NAME_LENGTH


def test_name_at_maximum_boundary_is_valid():
    assert validate_subject_name("A" * MAX_NAME_LENGTH) == "A" * MAX_NAME_LENGTH


def test_name_one_below_minimum_is_rejected():
    with pytest.raises(ValueError):
        validate_subject_name("A" * (MIN_NAME_LENGTH - 1))


def test_name_one_above_maximum_is_rejected():
    with pytest.raises(ValueError):
        validate_subject_name("A" * (MAX_NAME_LENGTH + 1))


def test_empty_name_is_rejected():
    with pytest.raises(ValueError):
        validate_subject_name("")


def test_whitespace_only_name_is_rejected():
    with pytest.raises(ValueError):
        validate_subject_name("   ")


def test_name_is_trimmed():
    assert validate_subject_name("  Matematika  ") == "Matematika"


@pytest.mark.parametrize("color", ["#FFFFFF", "#000000", "#4287f5", "#AbC123"])
def test_valid_hex_colors_accepted(color):
    assert validate_hex_color(color) == color


@pytest.mark.parametrize("color", ["FFFFFF", "#FFF", "#GGGGGG", "red", "#12345", "#1234567"])
def test_invalid_hex_colors_rejected(color):
    with pytest.raises(ValueError):
        validate_hex_color(color)


def test_none_color_is_allowed():
    assert validate_hex_color(None) is None
