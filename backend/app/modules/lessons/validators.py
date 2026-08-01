"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.lessons.constants import ALLOWED_URL_SCHEMES, MAX_TITLE_LENGTH, MIN_TITLE_LENGTH


def validate_lesson_title(title: str) -> str:
    stripped = title.strip()
    if not (MIN_TITLE_LENGTH <= len(stripped) <= MAX_TITLE_LENGTH):
        raise ValueError(f"Dars sarlavhasi {MIN_TITLE_LENGTH}-{MAX_TITLE_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_media_url(url: str | None) -> str | None:
    if url is None:
        return None
    stripped = url.strip()
    if not stripped.startswith(ALLOWED_URL_SCHEMES):
        raise ValueError(f"URL {' yoki '.join(ALLOWED_URL_SCHEMES)} bilan boshlanishi kerak")
    return stripped
