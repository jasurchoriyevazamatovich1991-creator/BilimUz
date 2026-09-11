"""Pure validation functions — no I/O, reusable from schemas or services."""
import bleach

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

# Sprint 32 — the exact rich-text toolbar capabilities requested
# (bold/italic/underline/headings/lists/links/paragraph alignment),
# nothing more. No <script>, <style>, event handlers (onclick etc.),
# <iframe>, or any other tag/attribute is on this list — bleach strips
# (does not merely escape) anything not explicitly allowed here, which
# is what actually prevents XSS rather than just hiding it visually.
RICH_TEXT_ALLOWED_TAGS = ["b", "strong", "i", "em", "u", "h1", "h2", "h3", "p", "br", "ol", "ul", "li", "a"]
RICH_TEXT_ALLOWED_ATTRIBUTES = {"a": ["href"]}
# NOTE: paragraph alignment (style="text-align: ...") was considered
# but deliberately NOT implemented — bleach.clean() does not sanitize
# CSS inside a style attribute without a separately configured
# CSSSanitizer, and allowing the raw attribute through without one
# would be a real, if narrow, injection surface. Left for a future
# sprint with a properly configured CSS allowlist rather than shipped
# as a half-implemented security control.


def sanitize_rich_text(html: str) -> str:
    """Strips everything except the approved rich-text toolbar's own
    output — the only defense that matters against XSS is an
    allowlist, not a denylist. Plain text (no HTML tags at all) passes
    through completely unchanged, so every existing question/option/
    explanation written before Sprint 32 keeps rendering exactly as
    before."""
    # ALLOWED_URL_SCHEMES stores full prefixes ("http://") for use
    # elsewhere in this module (URL-prefix validation) — bleach's
    # `protocols` parameter expects bare scheme names ("http"), so the
    # conversion happens locally here rather than changing the shared
    # constant's format for every other caller.
    bare_schemes = [scheme.rstrip("://") for scheme in ALLOWED_URL_SCHEMES]
    cleaned = bleach.clean(
        html, tags=RICH_TEXT_ALLOWED_TAGS, attributes=RICH_TEXT_ALLOWED_ATTRIBUTES,
        protocols=bare_schemes, strip=True,
    )
    return cleaned


def validate_question_text(text: str) -> str:
    stripped = text.strip()
    if not (MIN_QUESTION_TEXT_LENGTH <= len(stripped) <= MAX_QUESTION_TEXT_LENGTH):
        raise ValueError(f"Savol matni {MIN_QUESTION_TEXT_LENGTH}-{MAX_QUESTION_TEXT_LENGTH} belgidan iborat bo'lishi kerak")
    return sanitize_rich_text(stripped)


def validate_option_text(text: str) -> str:
    stripped = text.strip()
    if not (MIN_OPTION_TEXT_LENGTH <= len(stripped) <= MAX_OPTION_TEXT_LENGTH):
        raise ValueError(f"Variant matni {MIN_OPTION_TEXT_LENGTH}-{MAX_OPTION_TEXT_LENGTH} belgidan iborat bo'lishi kerak")
    return sanitize_rich_text(stripped)


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
