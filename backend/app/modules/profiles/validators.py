"""Pure validation functions — no I/O, reusable from schemas or services."""
from app.modules.profiles.constants import MAX_ADDRESS_LENGTH, MAX_BIO_LENGTH, MAX_SOCIAL_HANDLE_LENGTH, MAX_WEBSITE_LENGTH


def validate_bio(bio: str | None) -> str | None:
    if bio is None:
        return None
    stripped = bio.strip()
    if len(stripped) > MAX_BIO_LENGTH:
        raise ValueError(f"Bio {MAX_BIO_LENGTH} belgidan oshmasligi kerak")
    return stripped


def validate_address(address: str | None) -> str | None:
    if address is None:
        return None
    stripped = address.strip()
    if len(stripped) > MAX_ADDRESS_LENGTH:
        raise ValueError(f"Manzil {MAX_ADDRESS_LENGTH} belgidan oshmasligi kerak")
    return stripped


def validate_social_handle(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip().lstrip("@")
    if len(stripped) > MAX_SOCIAL_HANDLE_LENGTH:
        raise ValueError(f"Ijtimoiy tarmoq nomi {MAX_SOCIAL_HANDLE_LENGTH} belgidan oshmasligi kerak")
    return stripped


def validate_website(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if len(stripped) > MAX_WEBSITE_LENGTH:
        raise ValueError(f"Veb-sayt manzili {MAX_WEBSITE_LENGTH} belgidan oshmasligi kerak")
    return stripped
