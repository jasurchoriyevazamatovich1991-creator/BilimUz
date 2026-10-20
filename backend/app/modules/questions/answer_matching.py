"""
Task 2 — automatic grading for short-answer questions (IELTS gap-fill,
SAT grid-in, GRE numeric entry). Pure functions only: no I/O, no ORM,
so the same rules are used to VALIDATE an admin's accepted answers
(questions/service.py) and to GRADE a student's answer
(attempts/service.py), and can be unit-tested exhaustively.

Formats
-------
- "text":    normalized string equality against any accepted answer.
- "numeric": exact rational comparison against any accepted value,
             within an optional non-negative tolerance (inclusive).

Text normalization (applied identically to accepted answers and to the
student's answer):
  1. Unicode NFKC (full-width digits/letters, ligatures, non-breaking
     spaces become their ordinary forms);
  2. typographic apostrophes/quotes ’ ‘ ʼ ′ become a plain ' ;
  3. leading/trailing whitespace removed, inner whitespace runs
     collapsed to one space;
  4. casefold() unless the question is case-sensitive.
Punctuation is deliberately NOT stripped: "Paris." and "Paris" differ,
because silently discarding characters could turn a wrong answer into a
right one. Admins add variants they want to accept.

Numeric parsing (no floats anywhere — float equality/rounding could mark
a correct answer wrong):
  accepted:  12   -3   +4   3.25   .5   5.   7/2   -7/2   −2 (U+2212)
  rejected:  1,000  1.000,5  1e3  1 000  1/0  3.5/2  abc  ""  (and any
             string over MAX_NUMERIC_INPUT_LENGTH)
A rejected student input raises InvalidNumericAnswer; the caller refuses
to save it (HTTP 422) rather than scoring it as wrong.
"""
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from fractions import Fraction

ANSWER_FORMAT_TEXT = "text"
ANSWER_FORMAT_NUMERIC = "numeric"
ANSWER_FORMATS = (ANSWER_FORMAT_TEXT, ANSWER_FORMAT_NUMERIC)

MAX_ACCEPTED_ANSWERS = 20
MAX_ACCEPTED_ANSWER_LENGTH = 255
MAX_NUMERIC_INPUT_LENGTH = 40
# NUMERIC(20, 10) column: up to 10 integer digits and 10 decimal places.
MAX_TOLERANCE_INTEGER_DIGITS = 10
MAX_TOLERANCE_DECIMAL_PLACES = 10

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "′": "'"})
_WHITESPACE_RUN = re.compile(r"\s+")
_DECIMAL = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")
_FRACTION = re.compile(r"([+-]?\d+)/(\d+)")


class InvalidNumericAnswer(ValueError):
    """The string is not a number this grader accepts."""


class InvalidGradingConfiguration(ValueError):
    """An admin-supplied grading configuration breaks a rule below."""


# --- text --------------------------------------------------------------------

def normalize_text(value: str, case_sensitive: bool) -> str:
    normalized = unicodedata.normalize("NFKC", value).translate(_APOSTROPHES)
    normalized = _WHITESPACE_RUN.sub(" ", normalized).strip()
    return normalized if case_sensitive else normalized.casefold()


# --- numbers -------------------------------------------------------------------

def parse_number(value: str) -> Fraction:
    """Parse a student's or admin's numeric answer into an exact Fraction."""
    if not isinstance(value, str):
        raise InvalidNumericAnswer("Son matn ko'rinishida yuborilishi kerak")
    text = unicodedata.normalize("NFKC", value).replace("−", "-").strip()
    if not text:
        raise InvalidNumericAnswer("Son kiritilmagan")
    if len(text) > MAX_NUMERIC_INPUT_LENGTH:
        raise InvalidNumericAnswer("Son juda uzun")

    if _DECIMAL.fullmatch(text):
        return Fraction(Decimal(text))

    match = _FRACTION.fullmatch(text)
    if match:
        denominator = int(match.group(2))
        if denominator == 0:
            raise InvalidNumericAnswer("Kasrning maxraji 0 bo'lishi mumkin emas")
        return Fraction(int(match.group(1)), denominator)

    raise InvalidNumericAnswer(
        "Javob son bo'lishi kerak: butun son (12), o'nli kasr (3.5) yoki oddiy kasr (7/2). "
        "Vergul, bo'shliq va 1e3 ko'rinishi qabul qilinmaydi."
    )


def parse_tolerance(value) -> Fraction:
    """Tolerance comes from a NUMERIC column (Decimal) or an admin's input."""
    if value is None:
        return Fraction(0)
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise InvalidGradingConfiguration("Tolerance son bo'lishi kerak")
    if not decimal_value.is_finite():
        raise InvalidGradingConfiguration("Tolerance chekli son bo'lishi kerak")
    if decimal_value < 0:
        raise InvalidGradingConfiguration("Tolerance manfiy bo'lishi mumkin emas")
    return Fraction(decimal_value)


# --- grading ---------------------------------------------------------------------

def grade_short_answer(
    answer: str | None,
    answer_format: str | None,
    accepted_answers: list[str] | None,
    case_sensitive: bool = False,
    numeric_tolerance=None,
) -> bool | None:
    """Returns True/False for a gradable question, or None when there is
    nothing to grade (no configuration, or an empty answer — empty means
    unanswered, exactly like an unselected choice question).

    Raises InvalidNumericAnswer for a non-numeric answer to a numeric
    question, so the caller can reject it instead of marking it wrong."""
    if answer_format not in ANSWER_FORMATS or not accepted_answers:
        return None
    if answer is None or not answer.strip():
        return None

    if answer_format == ANSWER_FORMAT_TEXT:
        given = normalize_text(answer, case_sensitive)
        return any(given == normalize_text(a, case_sensitive) for a in accepted_answers)

    given_number = parse_number(answer)
    tolerance = parse_tolerance(numeric_tolerance)
    for accepted in accepted_answers:
        try:
            target = parse_number(accepted)
        except InvalidNumericAnswer:
            continue  # defensive: stored values are validated on write
        if abs(given_number - target) <= tolerance:
            return True
    return False


# --- admin configuration --------------------------------------------------------

def validate_grading_config(
    question_type: str,
    answer_format: str | None,
    accepted_answers: list[str] | None,
    case_sensitive: bool,
    numeric_tolerance,
) -> dict:
    """Validates the FINAL (merged) grading configuration of a question and
    returns the column values to store. Raises InvalidGradingConfiguration."""
    answers = [a for a in (accepted_answers or [])]

    if question_type != "short_answer":
        if answer_format is not None or answers or numeric_tolerance is not None or case_sensitive:
            raise InvalidGradingConfiguration("Avtomatik baholash sozlamalari faqat 'short_answer' savollari uchun")
        return {"answer_format": None, "accepted_answers": None, "case_sensitive": False, "numeric_tolerance": None}

    if answer_format is None:
        if answers or numeric_tolerance is not None:
            raise InvalidGradingConfiguration("To'g'ri javoblar yoki tolerance uchun answer_format tanlanishi kerak")
        return {"answer_format": None, "accepted_answers": None, "case_sensitive": bool(case_sensitive), "numeric_tolerance": None}

    if answer_format not in ANSWER_FORMATS:
        raise InvalidGradingConfiguration(f"answer_format quyidagilardan biri bo'lishi kerak: {', '.join(ANSWER_FORMATS)}")
    if not answers:
        raise InvalidGradingConfiguration("Kamida bitta to'g'ri javob kiritilishi kerak")
    if len(answers) > MAX_ACCEPTED_ANSWERS:
        raise InvalidGradingConfiguration(f"To'g'ri javoblar soni {MAX_ACCEPTED_ANSWERS} tadan oshmasligi kerak")

    cleaned: list[str] = []
    seen: set = set()
    for raw in answers:
        if not isinstance(raw, str):
            raise InvalidGradingConfiguration("Har bir to'g'ri javob matn bo'lishi kerak")
        value = raw.strip()
        if not value:
            raise InvalidGradingConfiguration("Bo'sh to'g'ri javob kiritilmasin")
        if len(value) > MAX_ACCEPTED_ANSWER_LENGTH:
            raise InvalidGradingConfiguration(f"To'g'ri javob {MAX_ACCEPTED_ANSWER_LENGTH} belgidan oshmasligi kerak")
        if answer_format == ANSWER_FORMAT_NUMERIC:
            try:
                key = parse_number(value)
            except InvalidNumericAnswer as exc:
                raise InvalidGradingConfiguration(f"'{value}' — noto'g'ri son: {exc}")
        else:
            key = normalize_text(value, case_sensitive)
        if key in seen:
            continue  # identical after normalization — keep the first spelling only
        seen.add(key)
        cleaned.append(value)

    if answer_format == ANSWER_FORMAT_TEXT:
        if numeric_tolerance is not None:
            raise InvalidGradingConfiguration("Tolerance faqat 'numeric' format uchun")
        return {"answer_format": ANSWER_FORMAT_TEXT, "accepted_answers": cleaned,
                "case_sensitive": bool(case_sensitive), "numeric_tolerance": None}

    if case_sensitive:
        raise InvalidGradingConfiguration("Katta-kichik harf sozlamasi faqat 'text' format uchun")
    tolerance_decimal = None
    if numeric_tolerance is not None:
        parse_tolerance(numeric_tolerance)  # sign/finite checks
        tolerance_decimal = numeric_tolerance if isinstance(numeric_tolerance, Decimal) else Decimal(str(numeric_tolerance).strip())
        sign, digits, exponent = tolerance_decimal.as_tuple()
        decimal_places = max(0, -exponent)
        integer_digits = max(0, len(digits) + exponent)
        if decimal_places > MAX_TOLERANCE_DECIMAL_PLACES or integer_digits > MAX_TOLERANCE_INTEGER_DIGITS:
            raise InvalidGradingConfiguration(
                f"Tolerance ko'pi bilan {MAX_TOLERANCE_INTEGER_DIGITS} butun va {MAX_TOLERANCE_DECIMAL_PLACES} kasr raqamdan iborat bo'lishi kerak"
            )
    return {"answer_format": ANSWER_FORMAT_NUMERIC, "accepted_answers": cleaned,
            "case_sensitive": False, "numeric_tolerance": tolerance_decimal}
