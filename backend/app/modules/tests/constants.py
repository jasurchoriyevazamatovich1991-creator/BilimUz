"""No magic numbers — every tunable value for this module lives here."""

MIN_TITLE_LENGTH = 2
MAX_TITLE_LENGTH = 255

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_SORT_FIELDS = ("title", "created_at", "duration")
DEFAULT_SORT_FIELD = "-created_at"

MIN_DURATION_MINUTES = 1
MAX_DURATION_MINUTES = 480  # 8 hours — generous ceiling, catches fat-fingered input

MIN_PASSING_SCORE = 0
MAX_PASSING_SCORE = 100  # percentage

# Status transitions allowed FROM each status — draft can go to published or
# archived; published can only be archived (never silently back to draft);
# archived is terminal.
ALLOWED_STATUS_TRANSITIONS = {
    "draft": {"published", "archived"},
    "published": {"archived"},
    "archived": set(),
}
