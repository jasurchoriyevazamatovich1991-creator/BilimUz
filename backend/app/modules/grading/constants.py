"""Task 5 — manual grading constants. No magic values elsewhere."""

# Permission (permissions/role_permissions tables) that lets a role view
# ungraded submissions and grade them. Seeded by migration 0026 for Admin
# and Super Admin only; other roles get it explicitly via Roles/Permissions.
GRADE_SUBMISSIONS_PERMISSION = "GRADE_SUBMISSIONS"

REVIEW_STATUS_DRAFT = "draft"
REVIEW_STATUS_FINALIZED = "finalized"
REVIEW_STATUS_SUPERSEDED = "superseded"
REVIEW_STATUSES = (REVIEW_STATUS_DRAFT, REVIEW_STATUS_FINALIZED, REVIEW_STATUS_SUPERSEDED)

# Queue filter values (derived, never stored).
QUEUE_STATUS_PENDING = "pending"        # no review yet
QUEUE_STATUS_DRAFT = "draft"            # a draft exists, nothing finalized
QUEUE_STATUS_FINALIZED = "finalized"    # a finalized review exists
QUEUE_STATUSES = (QUEUE_STATUS_PENDING, QUEUE_STATUS_DRAFT, QUEUE_STATUS_FINALIZED)

ROUNDING_HALF_UP = "half_up"
ROUNDING_FLOOR = "floor"
ROUNDING_MODES = (ROUNDING_HALF_UP, ROUNDING_FLOOR)

MAX_CRITERIA = 10
MAX_FEEDBACK_LENGTH = 5000
MAX_NOTES_LENGTH = 5000
MAX_INSTRUCTIONS_LENGTH = 10000
MAX_REASON_LENGTH = 1000

FINISHED_ATTEMPT_STATUSES = ("submitted", "auto_finished")
