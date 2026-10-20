"""Task 2 — pure grading rules (questions/answer_matching.py). No DB."""
from decimal import Decimal
from fractions import Fraction
from types import SimpleNamespace

import pytest

from app.modules.attempts.scoring import is_auto_gradable
from app.modules.questions.answer_matching import (
    InvalidGradingConfiguration,
    InvalidNumericAnswer,
    grade_short_answer,
    normalize_text,
    parse_number,
    validate_grading_config,
)


# --- text normalization ---------------------------------------------------------

@pytest.mark.parametrize("given", ["london", "London", "  LONDON ", "\tLondon\n", "Ｌｏｎｄｏｎ"])
def test_text_case_insensitive_whitespace_and_fullwidth(given):
    assert grade_short_answer(given, "text", ["London"]) is True


def test_text_inner_whitespace_collapsed():
    assert grade_short_answer("New    York", "text", ["new york"]) is True
    assert grade_short_answer("New York", "text", ["new york"]) is True


def test_text_inner_whitespace_not_removed_entirely():
    assert grade_short_answer("NewYork", "text", ["new york"]) is False


def test_text_typographic_apostrophe_matches_plain():
    assert grade_short_answer("don’t know", "text", ["don't know"]) is True


def test_text_punctuation_is_significant():
    assert grade_short_answer("Paris.", "text", ["Paris"]) is False


def test_text_case_sensitive_mode():
    assert grade_short_answer("ph", "text", ["pH"], case_sensitive=True) is False
    assert grade_short_answer(" pH ", "text", ["pH"], case_sensitive=True) is True


def test_text_multiple_accepted_answers():
    accepted = ["colour", "color"]
    assert grade_short_answer("Color", "text", accepted) is True
    assert grade_short_answer("colours", "text", accepted) is False


def test_text_wrong_answer():
    assert grade_short_answer("Berlin", "text", ["London"]) is False


@pytest.mark.parametrize("empty", [None, "", "   ", "\n"])
def test_empty_answer_is_unanswered_not_wrong(empty):
    assert grade_short_answer(empty, "text", ["x"]) is None
    assert grade_short_answer(empty, "numeric", ["1"]) is None


def test_unconfigured_question_is_not_graded():
    assert grade_short_answer("anything", None, ["x"]) is None
    assert grade_short_answer("anything", "text", []) is None
    assert grade_short_answer("anything", "text", None) is None
    assert grade_short_answer("anything", "regex", ["x"]) is None


def test_normalize_text_is_idempotent():
    once = normalize_text("  Ｈｅｌｌｏ’  World ", False)
    assert normalize_text(once, False) == once == "hello' world"


# --- numeric parsing -----------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("12", Fraction(12)), ("-3", Fraction(-3)), ("+4", Fraction(4)), ("3.25", Fraction(13, 4)),
    (".5", Fraction(1, 2)), ("5.", Fraction(5)), ("7/2", Fraction(7, 2)), ("-7/2", Fraction(-7, 2)),
    ("−2", Fraction(-2)), (" 0.1 ", Fraction(1, 10)), ("１２", Fraction(12)), ("0", Fraction(0)),
])
def test_parse_number_accepts(text, expected):
    assert parse_number(text) == expected


@pytest.mark.parametrize("text", [
    "", "   ", "abc", "1,000", "1,5", "1.000,5", "1e3", "1E3", "1 000", "1/0", "3.5/2", "1/-2", "--1", "1..2",
    "nan", "inf", "0x10", "½", "1" * 41,
])
def test_parse_number_rejects(text):
    with pytest.raises(InvalidNumericAnswer):
        parse_number(text)


# --- numeric grading -------------------------------------------------------------------

def test_numeric_exact_match_without_float_error():
    # 0.1 + 0.2 != 0.3 in binary floating point; exact rationals avoid it.
    assert grade_short_answer("0.3", "numeric", ["0.3"]) is True
    assert grade_short_answer(".30", "numeric", ["0.3"]) is True


def test_numeric_fraction_equals_decimal():
    assert grade_short_answer("7/2", "numeric", ["3.5"]) is True
    assert grade_short_answer("3.5", "numeric", ["7/2"]) is True
    assert grade_short_answer("14/4", "numeric", ["3.5"]) is True


def test_numeric_without_tolerance_requires_exact_value():
    assert grade_short_answer("0.667", "numeric", ["2/3"]) is False


def test_numeric_tolerance_boundary_is_inclusive():
    # |0.667 - 2/3| = 1/3000 = 0.000333...
    assert grade_short_answer("0.667", "numeric", ["2/3"], numeric_tolerance=Decimal("0.001")) is True
    assert grade_short_answer("1.5", "numeric", ["1"], numeric_tolerance=Decimal("0.5")) is True
    assert grade_short_answer("0.5", "numeric", ["1"], numeric_tolerance=Decimal("0.5")) is True
    assert grade_short_answer("1.5000000001", "numeric", ["1"], numeric_tolerance=Decimal("0.5")) is False
    assert grade_short_answer("0.4999999999", "numeric", ["1"], numeric_tolerance=Decimal("0.5")) is False


def test_numeric_tolerance_from_db_numeric_with_trailing_zeros():
    assert grade_short_answer("10.01", "numeric", ["10"], numeric_tolerance=Decimal("0.0100000000")) is True
    assert grade_short_answer("10.0100001", "numeric", ["10"], numeric_tolerance=Decimal("0.0100000000")) is False


def test_numeric_multiple_accepted_values():
    accepted = ["2/3", "0.666", "0.667"]
    assert grade_short_answer(".666", "numeric", accepted) is True
    assert grade_short_answer(".667", "numeric", accepted) is True
    assert grade_short_answer(".66", "numeric", accepted) is False


def test_numeric_negative_values():
    assert grade_short_answer("-4", "numeric", ["-4"]) is True
    assert grade_short_answer("4", "numeric", ["-4"]) is False


def test_numeric_invalid_student_input_raises_instead_of_grading_wrong():
    with pytest.raises(InvalidNumericAnswer):
        grade_short_answer("1,5", "numeric", ["1.5"])


# --- admin configuration validation ---------------------------------------------------------

def test_config_text_ok_and_deduplicated_after_normalization():
    out = validate_grading_config("short_answer", "text", [" color ", "Color", "colour"], False, None)
    assert out == {"answer_format": "text", "accepted_answers": ["color", "colour"], "case_sensitive": False, "numeric_tolerance": None}


def test_config_text_case_sensitive_keeps_case_variants():
    out = validate_grading_config("short_answer", "text", ["pH", "PH"], True, None)
    assert out["accepted_answers"] == ["pH", "PH"]


def test_config_numeric_ok_with_tolerance():
    out = validate_grading_config("short_answer", "numeric", ["2/3", "0.667"], False, Decimal("0.001"))
    assert out["answer_format"] == "numeric" and out["numeric_tolerance"] == Decimal("0.001")


def test_config_numeric_equivalent_values_deduplicated():
    out = validate_grading_config("short_answer", "numeric", ["0.5", "1/2", ".50"], False, None)
    assert out["accepted_answers"] == ["0.5"]


def test_config_none_clears_everything():
    out = validate_grading_config("short_answer", None, None, False, None)
    assert out["answer_format"] is None and out["accepted_answers"] is None


@pytest.mark.parametrize("args", [
    ("essay", "text", ["x"], False, None),
    ("single_choice", None, ["x"], False, None),
    ("single_choice", None, None, True, None),
    ("short_answer", None, ["x"], False, None),
    ("short_answer", None, None, False, Decimal("1")),
    ("short_answer", "regex", ["x"], False, None),
    ("short_answer", "text", [], False, None),
    ("short_answer", "text", None, False, None),
    ("short_answer", "text", ["  "], False, None),
    ("short_answer", "text", ["x" * 256], False, None),
    ("short_answer", "text", [str(i) for i in range(21)], False, None),
    ("short_answer", "text", ["x"], False, Decimal("0.1")),
    ("short_answer", "numeric", ["abc"], False, None),
    ("short_answer", "numeric", ["1,5"], False, None),
    ("short_answer", "numeric", ["1"], True, None),
    ("short_answer", "numeric", ["1"], False, Decimal("-0.1")),
    ("short_answer", "numeric", ["1"], False, Decimal("0.00000000001")),
    ("short_answer", "numeric", ["1"], False, Decimal("12345678901")),
    ("short_answer", "numeric", ["1"], False, Decimal("NaN")),
])
def test_config_rejected(args):
    with pytest.raises(InvalidGradingConfiguration):
        validate_grading_config(*args)


# --- is_auto_gradable ---------------------------------------------------------------------------

@pytest.mark.parametrize("qtype", ["single_choice", "multiple_choice", "true_false"])
def test_choice_types_always_auto_gradable(qtype):
    assert is_auto_gradable(SimpleNamespace(question_type=qtype)) is True


def test_short_answer_auto_gradable_only_when_configured():
    assert is_auto_gradable(SimpleNamespace(question_type="short_answer", answer_format="text", accepted_answers=["a"])) is True
    assert is_auto_gradable(SimpleNamespace(question_type="short_answer", answer_format=None, accepted_answers=None)) is False
    assert is_auto_gradable(SimpleNamespace(question_type="short_answer", answer_format="text", accepted_answers=[])) is False
    assert is_auto_gradable(SimpleNamespace(question_type="short_answer")) is False


def test_essay_never_auto_gradable():
    assert is_auto_gradable(SimpleNamespace(question_type="essay", answer_format="text", accepted_answers=["a"])) is False
