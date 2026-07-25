"""No magic numbers — every tunable value for this module lives here."""

MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 50

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_SORT_FIELDS = ("name", "created_at")
DEFAULT_SORT_FIELD = "name"

# The 8 roles seeded by database/schema/schema_v2.sql. These define the
# platform's core privilege structure — they can never be renamed or
# deleted through the API, only deactivated (status), to guarantee
# require_roles("Admin"), require_roles("Super Admin") etc. across the
# whole codebase never silently break.
SYSTEM_ROLE_NAMES = (
    "Super Admin", "Admin", "Moderator", "Teacher",
    "Applicant", "Student", "Parent", "Guest",
)
