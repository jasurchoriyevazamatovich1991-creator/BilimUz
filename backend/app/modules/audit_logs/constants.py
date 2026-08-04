"""No magic numbers — every tunable value for this module lives here."""

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

MAX_DATE_RANGE_DAYS = 90  # approved decision — proactive guard against
                          # an unbounded query over a table with 34 write
                          # call sites across 20 modules
