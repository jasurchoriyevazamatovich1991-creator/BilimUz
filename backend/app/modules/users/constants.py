"""No magic numbers — every tunable value for this module lives here."""

MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 100

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_SORT_FIELDS = ("first_name", "last_name", "created_at", "last_login")
DEFAULT_SORT_FIELD = "-created_at"

# Only these statuses can be set via the admin update endpoint — "banned"
# has its own dedicated endpoint (ban_user) so it's always paired with an
# audit-logged reason, never silently set through a generic PATCH.
ADMIN_SETTABLE_STATUSES = ("active", "inactive")
