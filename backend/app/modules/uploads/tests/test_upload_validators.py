"""Unit tests for pure classification/sanitization functions — no I/O."""
from app.modules.uploads.constants import FILE_TYPE_AUDIO, FILE_TYPE_DOCUMENT, FILE_TYPE_IMAGE, FILE_TYPE_VIDEO, MAX_SIZE_IMAGE
from app.modules.uploads.validators import classify_content_type, extension_for_content_type, sanitize_display_filename


def test_classify_image_returns_correct_category_and_size():
    result = classify_content_type("image/png")
    assert result == (FILE_TYPE_IMAGE, MAX_SIZE_IMAGE)


def test_classify_pdf_returns_document_category():
    file_type, _ = classify_content_type("application/pdf")
    assert file_type == FILE_TYPE_DOCUMENT


def test_classify_office_doc_returns_document_category():
    file_type, _ = classify_content_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert file_type == FILE_TYPE_DOCUMENT


def test_classify_audio_returns_audio_category():
    file_type, _ = classify_content_type("audio/mpeg")
    assert file_type == FILE_TYPE_AUDIO


def test_classify_video_returns_video_category():
    file_type, _ = classify_content_type("video/mp4")
    assert file_type == FILE_TYPE_VIDEO


def test_classify_unknown_type_returns_none():
    assert classify_content_type("application/x-executable") is None


def test_classify_rejects_disguised_executable():
    """Allowlist, not a denylist — anything not explicitly known is
    rejected, including something an attacker might hope slips through."""
    assert classify_content_type("application/octet-stream") is None


def test_sanitize_strips_control_characters():
    assert sanitize_display_filename("file\x00name.pdf") == "filename.pdf"


def test_sanitize_empty_name_falls_back():
    assert sanitize_display_filename("") == "file"


def test_extension_lookup_known_type():
    assert extension_for_content_type("image/png") == ".png"


def test_extension_lookup_unknown_type_returns_empty():
    assert extension_for_content_type("application/x-mystery") == ""
