"""No magic numbers — every tunable value for this module lives here."""

MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 150
HEX_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_STATUS_VALUES = ("active", "inactive", "archived")
ALLOWED_SORT_FIELDS = ("name", "created_at", "updated_at")
DEFAULT_SORT_FIELD = "-created_at"  # "-" prefix = descending
