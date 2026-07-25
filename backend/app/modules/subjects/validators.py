"""Pure validation functions — no I/O, reusable from schemas or services."""
import re

from app.modules.subjects.constants import HEX_COLOR_PATTERN, MAX_NAME_LENGTH, MIN_NAME_LENGTH

_COLOR_RE = re.compile(HEX_COLOR_PATTERN)


def validate_subject_name(name: str) -> str:
    stripped = name.strip()
    if not (MIN_NAME_LENGTH <= len(stripped) <= MAX_NAME_LENGTH):
        raise ValueError(f"Fan nomi {MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} belgidan iborat bo'lishi kerak")
    return stripped


def validate_hex_color(color: str | None) -> str | None:
    if color is None:
        return None
    if not _COLOR_RE.match(color):
        raise ValueError("Rang #RRGGBB formatida bo'lishi kerak (masalan #4287f5)")
    return color
