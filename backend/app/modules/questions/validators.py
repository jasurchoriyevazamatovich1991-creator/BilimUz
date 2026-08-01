"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.questions.constants import (
    ALLOWED_URL_SCHEMES,
    CHOICE_QUESTION_TYPES,
    MAX_OPTION_TEXT_LENGTH,
    MAX_QUESTION_TEXT_LENGTH,
    MAX_SCORE,
    MIN_OPTIONS_FOR_CHOICE_QUESTION,
    MIN_OPTION_TEXT_LENGTH,
    MIN_QUESTION_TEXT_LENGTH,
    MIN_SCORE,
)


def validate_question_text(text: str) -> str:
    stripped = text.strip()
    if not (MIN_QUESTION_TEXT_LENGTH <= len(stripped) <= MAX_QUESTION_TEXT_LENGTH):
        raise ValueError(f"Savol matni {MIN_QUESTION_TEXT_LENGTH}-{MAX_QUESTION_TEXT_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_option_text(text: str) -> str:
    stripped = text.strip()
    if not (MIN_OPTION_TEXT_LENGTH <= len(stripped) <= MAX_OPTION_TEXT_LENGTH):
        raise ValueError(f"Variant matni {MIN_OPTION_TEXT_LENGTH}-{MAX_OPTION_TEXT_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_score(score: float) -> float:
    if not (MIN_SCORE <= score <= MAX_SCORE):
        raise ValueError(f"Ball {MIN_SCORE}-{MAX_SCORE} oralig'ida bo'lishi kerak")
    return score


def validate_media_url(url: str) -> str:
    stripped = url.strip()
    if not stripped.startswith(ALLOWED_URL_SCHEMES):
        raise ValueError(f"URL {' yoki '.join(ALLOWED_URL_SCHEMES)} bilan boshlanishi kerak")
    return stripped


def validate_option_set(question_type: str, options: list[dict]) -> None:
    """Cross-field rule that can't live in a single-field Pydantic
    validator — checked explicitly in the service layer at question
    creation time. `options` is a list of {"is_correct": bool} dicts."""
    if question_type not in CHOICE_QUESTION_TYPES:
        return  # essay/short_answer — no options expected

    if len(options) < MIN_OPTIONS_FOR_CHOICE_QUESTION:
        raise ValueError(f"'{question_type}' turidagi savol kamida {MIN_OPTIONS_FOR_CHOICE_QUESTION} ta variantga ega bo'lishi kerak")

    correct_count = sum(1 for o in options if o.get("is_correct"))
    if question_type in ("single_choice", "true_false") and correct_count != 1:
        raise ValueError(f"'{question_type}' turida aynan 1 ta to'g'ri variant bo'lishi kerak, {correct_count} ta topildi")
    if question_type == "multiple_choice" and correct_count < 1:
        raise ValueError("'multiple_choice' turida kamida 1 ta to'g'ri variant bo'lishi kerak")
