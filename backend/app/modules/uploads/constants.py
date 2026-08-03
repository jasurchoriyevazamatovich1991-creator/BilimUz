"""No magic numbers — every tunable value for this module lives here.
File size limits per the approved Sprint 8 decisions."""

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

MB = 1024 * 1024

MAX_SIZE_IMAGE = 10 * MB
MAX_SIZE_PDF = 20 * MB
MAX_SIZE_OFFICE_DOCUMENT = 20 * MB
MAX_SIZE_AUDIO = 50 * MB
MAX_SIZE_VIDEO = 200 * MB

# category -> (allowed MIME types, max size). Allowlist, not a denylist —
# anything not listed here is rejected, no exceptions.
IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
PDF_MIME_TYPES = {"application/pdf"}
OFFICE_MIME_TYPES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
AUDIO_MIME_TYPES = {"audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4"}
VIDEO_MIME_TYPES = {"video/mp4", "video/webm", "video/quicktime"}

FILE_TYPE_IMAGE = "image"
FILE_TYPE_DOCUMENT = "document"
FILE_TYPE_AUDIO = "audio"
FILE_TYPE_VIDEO = "video"
