"""No magic numbers — every tunable value for this module lives here."""

MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 255
MIN_OWNER_NAME_LENGTH = 2
MAX_OWNER_NAME_LENGTH = 255

MAX_REGION_LENGTH = 100

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_SORT_FIELDS = ("name", "region", "created_at")
DEFAULT_SORT_FIELD = "name"

ALLOWED_STATUS_VALUES = ("active", "inactive", "archived")
