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
# Sprint 27 Amendment: raised from 200 MB to 2 GB to support real
# lesson videos. Large videos use R2 Multipart Upload instead of a
# single PUT — see MULTIPART_THRESHOLD_BYTES below — so raising this
# limit does not mean a 2 GB single request is ever attempted.
GB = 1024 * MB
MAX_SIZE_VIDEO = 2 * GB

# Sprint 29 — Critical fix. The LEGACY, backend-mediated POST /uploads
# endpoint must NOT allow a video anywhere near the R2/multipart 2 GB
# ceiling above — that endpoint reads bytes through this server's own
# process, unlike the presigned/multipart flow where the browser talks
# to R2 directly. This limit applies ONLY to video sent through the
# legacy endpoint; MAX_SIZE_VIDEO (R2/multipart) is completely
# unchanged, and every other file type's existing legacy limit
# (image/PDF/audio, all already well under 100 MB) is untouched —
# those were never the actual risk.
LEGACY_UPLOAD_MAX_VIDEO_SIZE = 20 * MB

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

# Sprint 27 — status values for the presigned (direct-to-R2) upload
# flow. Reuses the existing StatusMixin `status` column (free-text
# string, no migration needed) — the original synchronous POST /uploads
# flow still uses StatusMixin's own default "active" and never sets
# these, so it is completely unaffected.
UPLOAD_STATUS_PENDING = "pending"   # session created, browser has not confirmed the R2 PUT finished yet
UPLOAD_STATUS_READY = "ready"       # finalized — safe to generate view URLs for
UPLOAD_STATUS_FAILED = "failed"     # explicitly marked failed (not currently auto-set — no failure webhook exists)

# Presigned URL TTLs, in seconds.
PRESIGNED_UPLOAD_TTL_SECONDS = 15 * 60   # 15 min — enough for a large video PUT to start and complete
PRESIGNED_DOWNLOAD_TTL_SECONDS = 5 * 60  # 5 min — short-lived view/play access, matches "short TTL" requirement

# Sprint 27 Amendment — R2 Multipart Upload configuration. Centralized
# here (not hardcoded in the service/router/frontend) so the threshold
# and part size are each defined exactly once.
#
# MULTIPART_THRESHOLD_BYTES: files at or below this use the existing
# single presigned PUT (unchanged); above it, multipart is used.
MULTIPART_THRESHOLD_BYTES = 100 * MB

# MULTIPART_PART_SIZE_BYTES: S3/R2 requires every part except the last
# to be >= 5 MB, and a maximum of 10,000 parts per upload. At 20 MB/part,
# the 2 GB video ceiling needs at most ceil(2GB / 20MB) = 103 parts —
# comfortably within the 10,000-part limit with a lot of headroom, while
# still keeping each individual part small enough to retry cheaply if
# one fails (see MULTIPART_PART_RETRY_LIMIT).
MULTIPART_PART_SIZE_BYTES = 20 * MB

# MAX_CONCURRENT_PARTS: how many parts the browser uploads in parallel.
# Bounded deliberately — unbounded concurrency would risk browser
# resource exhaustion and hammering R2 with simultaneous requests for a
# single upload.
MAX_CONCURRENT_PARTS = 4

# A single part is retried this many times (independently of every
# other part) before the whole upload is marked failed — never restart
# the entire multi-gigabyte upload because one part had a transient
# network error.
MULTIPART_PART_RETRY_LIMIT = 3

# S3/R2's own hard ceiling — validated defensively even though our real
# part-count-at-max-size never gets close to it.
MULTIPART_MAX_PART_NUMBER = 10_000
