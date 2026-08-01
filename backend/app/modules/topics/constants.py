"""No magic numbers — every tunable value for this module lives here."""

MIN_TITLE_LENGTH = 2
MAX_TITLE_LENGTH = 255

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_SORT_FIELDS = ("title", "order_number", "created_at")
DEFAULT_SORT_FIELD = "order_number"

ALLOWED_STATUS_VALUES = ("active", "inactive", "archived")

DEFAULT_ORDER_NUMBER = 0
