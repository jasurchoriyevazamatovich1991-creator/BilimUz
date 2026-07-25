"""No magic numbers — every tunable value for this module lives here."""
import re

MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 150

# Permission codes follow SCREAMING_SNAKE_CASE — e.g. CREATE_TEST,
# DELETE_USER, VIEW_ANALYTICS. Enforced so require_permission("code")
# calls across the codebase stay visually consistent and grep-able.
CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,99}$")

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_SORT_FIELDS = ("code", "module", "created_at")
DEFAULT_SORT_FIELD = "module"

# Matches the 25-module map in .cursor/context/05-system-modules.md —
# kept here (not imported from there, since that's a doc, not code) so
# `module` on a Permission can be validated against a known list.
KNOWN_MODULES = (
    "authentication", "users", "roles", "permissions", "subjects", "grades",
    "topics", "lessons", "tests", "questions", "results", "certificates",
    "ai", "notifications", "payments", "analytics", "settings", "uploads",
)
