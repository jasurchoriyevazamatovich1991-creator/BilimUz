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
# Task 10.1 — longest accepted Speaking recording (matches the recorder's
# 15-minute cap), enforced server-side from the decoded audio packets.
SPEAKING_AUDIO_MAX_SECONDS = 15 * 60
# Codec framing/padding makes a take the recorder stopped at exactly 15:00
# measure a few milliseconds longer (e.g. 900.014 s for Opus), so a small
# grace keeps a full-length answer from being rejected.
SPEAKING_AUDIO_DURATION_GRACE_SECONDS = 2
SPEAKING_AUDIO_MAX_BYTES = 20 * 1024 * 1024
SPEAKING_COMPONENT = "ielts_speaking"


def audio_content_matches(mime: str, data: bytes) -> bool:
    """Task 10 — the file's leading bytes must match the declared audio type
    (container signature), so arbitrary content can't be stored and served
    back as audio just by labelling it. Not a full decoder: a correctly
    signed but corrupt file still passes and simply won't play."""
    if mime == "audio/webm":
        return data[:4] == b"\x1aE\xdf\xa3"                       # EBML
    if mime == "audio/ogg":
        return data[:4] == b"OggS"
    if mime == "audio/mp4":
        return len(data) >= 12 and data[4:8] == b"ftyp"
    if mime == "audio/mpeg":
        return data[:3] == b"ID3" or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)
    if mime in ("audio/wav", "audio/x-wav"):
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    return False
