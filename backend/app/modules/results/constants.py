"""No magic numbers — every tunable value for this module lives here."""

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_SORT_FIELDS = ("created_at", "percentage")
DEFAULT_SORT_FIELD = "-created_at"

ALLOWED_PERIODS = ("daily", "weekly", "monthly", "all_time")
DEFAULT_PERIOD = "all_time"

RESULT_STATUS_FINAL = "final"
