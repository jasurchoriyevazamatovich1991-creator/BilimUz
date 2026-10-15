"""No magic numbers — every tunable value for this module lives here."""

MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 255

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_SORT_FIELDS = ("name", "created_at", "price")
DEFAULT_SORT_FIELD = "-created_at"

# Mirrors tests.models.TestStatus's own draft/published/archived
# lifecycle (the one existing precedent for a real publication-status
# enum in this codebase) — deliberately NOT the generic StatusMixin
# active/inactive, since a catalog product needs the same draft-before-
# visible workflow Test already has.
PRODUCT_STATUS_DRAFT = "draft"
PRODUCT_STATUS_PUBLISHED = "published"
PRODUCT_STATUS_ARCHIVED = "archived"
ALLOWED_PRODUCT_STATUS_VALUES = (PRODUCT_STATUS_DRAFT, PRODUCT_STATUS_PUBLISHED, PRODUCT_STATUS_ARCHIVED)

# Spec §4 — "Grade subscriptions, mock tests, and exam-preparation
# courses are independent products." Three product types this phase
# models; "course" covers IELTS/SAT/GRE for now (no separate Course
# catalog entity yet — see README "Deferred to a later phase").
PRODUCT_TYPE_GRADE_SUBSCRIPTION = "grade_subscription"
PRODUCT_TYPE_MOCK_TEST = "mock_test"
PRODUCT_TYPE_COURSE = "course"
ALLOWED_PRODUCT_TYPES = (PRODUCT_TYPE_GRADE_SUBSCRIPTION, PRODUCT_TYPE_MOCK_TEST, PRODUCT_TYPE_COURSE)
