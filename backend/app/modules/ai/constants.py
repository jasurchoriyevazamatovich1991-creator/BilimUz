"""No magic numbers — every tunable value for this module lives here.
Rate limit and message length per the approved Sprint 9 decisions."""

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

MESSAGE_RATE_LIMIT_MAX_REQUESTS = 10
MESSAGE_RATE_LIMIT_WINDOW_SECONDS = 60

MAX_MESSAGE_LENGTH = 4000

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ALLOWED_HISTORY_ROLES = (ROLE_USER, ROLE_ASSISTANT)

MAX_HISTORY_MESSAGES_FOR_CONTEXT = 20  # how many prior turns are sent to the provider as context
