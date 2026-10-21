"""No magic numbers — every tunable value for this module lives here."""

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

# Statuses considered "still active" — a lazy-expiry check only matters
# for these; submitted/auto_finished/cancelled attempts are terminal.
ACTIVE_STATUSES = ("in_progress", "paused")

# Default max attempts per user per test when tests.max_attempts is not
# set (the referenced schema design allows it to be null = unlimited in
# some designs, but BilimUz's default policy is "1 unless a test says
# otherwise" — matches docs/API/api_blueprint.md's original business rule).
DEFAULT_MAX_ATTEMPTS = 1


# --- Task 6: IELTS Speaking audio responses ---
# Formats MediaRecorder actually produces (Chrome/Firefox: webm/ogg opus;
# Safari: mp4/aac) plus common uploads. Value = stored file extension.
SPEAKING_AUDIO_MIME_TYPES = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}
SPEAKING_AUDIO_EXTENSION_MIME = {".webm": "audio/webm", ".ogg": "audio/ogg", ".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav"}
# One Speaking part is a few minutes; 20 MB is ample for opus/aac and well
# under the uploads module's general 50 MB audio limit.
SPEAKING_AUDIO_MAX_BYTES = 20 * 1024 * 1024
SPEAKING_COMPONENT = "ielts_speaking"
