"""No magic numbers — every tunable value for this module lives here."""

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

MAX_DATE_RANGE_DAYS = 90  # approved decision, same cap as audit_logs

ALLOWED_LEVELS = ("info", "warning", "error", "critical")

MAX_MESSAGE_LENGTH = 2000
MAX_SOURCE_LENGTH = 100
