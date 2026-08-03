"""Pure validation functions — no I/O. Classifying a MIME type and
checking it against the allowlist+size-limit pair lives here so it's
unit-testable without touching the filesystem."""
from app.modules.uploads.constants import (
    AUDIO_MIME_TYPES,
    FILE_TYPE_AUDIO,
    FILE_TYPE_DOCUMENT,
    FILE_TYPE_IMAGE,
    FILE_TYPE_VIDEO,
    IMAGE_MIME_TYPES,
    MAX_SIZE_AUDIO,
    MAX_SIZE_IMAGE,
    MAX_SIZE_OFFICE_DOCUMENT,
    MAX_SIZE_PDF,
    MAX_SIZE_VIDEO,
    OFFICE_MIME_TYPES,
    PDF_MIME_TYPES,
    VIDEO_MIME_TYPES,
)


def classify_content_type(content_type: str) -> tuple[str, int] | None:
    """Returns (file_type_category, max_size_bytes), or None if the MIME
    type isn't on the allowlist — allowlist, not a denylist, by design."""
    if content_type in IMAGE_MIME_TYPES:
        return FILE_TYPE_IMAGE, MAX_SIZE_IMAGE
    if content_type in PDF_MIME_TYPES:
        return FILE_TYPE_DOCUMENT, MAX_SIZE_PDF
    if content_type in OFFICE_MIME_TYPES:
        return FILE_TYPE_DOCUMENT, MAX_SIZE_OFFICE_DOCUMENT
    if content_type in AUDIO_MIME_TYPES:
        return FILE_TYPE_AUDIO, MAX_SIZE_AUDIO
    if content_type in VIDEO_MIME_TYPES:
        return FILE_TYPE_VIDEO, MAX_SIZE_VIDEO
    return None


def sanitize_display_filename(file_name: str) -> str:
    """Strips control characters for DISPLAY purposes only — the actual
    on-disk storage name is always a generated UUID (see storage.py),
    never derived from this value, so this is a display-safety measure,
    not a path-traversal defense (that's structural, not sanitization-based)."""
    return "".join(ch for ch in file_name if ch.isprintable()).strip() or "file"


def extension_for_content_type(content_type: str) -> str:
    """Minimal, explicit mapping — not guessing from the original
    filename (which is untrusted input)."""
    mapping = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
        "application/pdf": ".pdf",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.ms-excel": ".xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.ms-powerpoint": ".ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
        "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
    }
    return mapping.get(content_type, "")
