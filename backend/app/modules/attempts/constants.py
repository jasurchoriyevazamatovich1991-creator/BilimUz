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
