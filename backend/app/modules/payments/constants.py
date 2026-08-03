"""No magic numbers — every tunable value for this module lives here."""

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

ALLOWED_CURRENCIES = ("UZS",)
MIN_AMOUNT = 0.01

MIN_PLAN_NAME_LENGTH = 2
MAX_PLAN_NAME_LENGTH = 100
MIN_DURATION_DAYS = 1

ALLOWED_PROVIDERS = ("click", "payme", "uzum_bank", "humo", "uzcard", "stripe")

# Refunds: full-only this sprint (approved decision) — no partial-amount support.
