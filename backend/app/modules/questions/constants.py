"""No magic numbers — every tunable value for this module lives here."""

MIN_QUESTION_TEXT_LENGTH = 3
MAX_QUESTION_TEXT_LENGTH = 5000

MIN_OPTION_TEXT_LENGTH = 1
MAX_OPTION_TEXT_LENGTH = 1000

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_SORT_FIELDS = ("created_at", "difficulty")
DEFAULT_SORT_FIELD = "created_at"

MIN_SCORE = 0.01
MAX_SCORE = 1000

# Question types that require options at all — essay/short_answer are
# free-text, no options attached.
CHOICE_QUESTION_TYPES = ("single_choice", "multiple_choice", "true_false")
MIN_OPTIONS_FOR_CHOICE_QUESTION = 2

ALLOWED_QUESTION_TYPES = ("single_choice", "multiple_choice", "true_false", "short_answer", "essay")
ALLOWED_DIFFICULTY_LEVELS = ("easy", "medium", "hard")
ALLOWED_MEDIA_TYPES = ("image", "audio", "video", "formula")
ALLOWED_URL_SCHEMES = ("http://", "https://")
