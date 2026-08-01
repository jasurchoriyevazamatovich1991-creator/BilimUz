"""No magic numbers — every tunable value for this module lives here."""

MIN_TITLE_LENGTH = 2
MAX_TITLE_LENGTH = 255

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_SORT_FIELDS = ("title", "created_at")
DEFAULT_SORT_FIELD = "created_at"

ALLOWED_STATUS_VALUES = ("active", "inactive", "archived")

# A lesson must have at least one form of content — an empty lesson
# (no video, no pdf, no text) is not a valid lesson.
ALLOWED_URL_SCHEMES = ("http://", "https://")
