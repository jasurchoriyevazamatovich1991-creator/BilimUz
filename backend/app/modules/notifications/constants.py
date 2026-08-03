"""No magic numbers — every tunable value for this module lives here."""

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_CHANNELS = ("in_app", "email", "sms")

DEFAULT_QUEUE_BATCH_SIZE = 50
MAX_QUEUE_BATCH_SIZE = 200
MAX_SEND_ATTEMPTS = 5  # a row past this many failures stops retrying

MAX_TITLE_LENGTH = 255
MAX_TEMPLATE_CODE_LENGTH = 100
