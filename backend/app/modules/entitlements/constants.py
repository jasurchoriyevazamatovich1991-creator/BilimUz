"""No magic numbers — every tunable value for this module lives here."""

SOURCE_PURCHASE = "purchase"
SOURCE_ADMIN_GRANT = "admin_grant"
ALLOWED_SOURCE_VALUES = (SOURCE_PURCHASE, SOURCE_ADMIN_GRANT)

STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"
STATUS_REVOKED = "revoked"
ALLOWED_STATUS_VALUES = (STATUS_ACTIVE, STATUS_EXPIRED, STATUS_REVOKED)

# Admin Management of Mock Test Entitlements (Task D).
#
# EFFECTIVE status values are NOT stored on the row — they are computed
# at read time from the stored `status` + `start_date`/`end_date`
# (see service.py's `_effective_status()`). "scheduled" in particular
# is deliberately not a stored enum value: adding it to the DB enum
# would mean a background job has to flip scheduled->active the moment
# start_date arrives, which does not exist in this codebase (nothing
# here runs on a clock — every existing lazy-transition, e.g. attempts'
# auto-finish, is computed on read, never on a timer). Computing it on
# read keeps the same "no background jobs" architecture and guarantees
# the value is always correct, never stale.
EFFECTIVE_STATUS_SCHEDULED = "scheduled"
EFFECTIVE_STATUS_ACTIVE = STATUS_ACTIVE
EFFECTIVE_STATUS_EXPIRED = STATUS_EXPIRED
EFFECTIVE_STATUS_REVOKED = STATUS_REVOKED

MAX_REASON_LENGTH = 500

# Admin-grant duration presets the UI offers (spec §2.5 — "30 days, 90
# days, or one year if compatible with existing date-handling
# conventions"). Not DB-enforced — `duration_days` on the grant/extend
# request is a plain positive integer, exactly like
# CatalogProduct.duration_days already is, so a future preset (e.g. 180
# days) needs no backend change, only a frontend dropdown option.
SUGGESTED_DURATION_DAYS = (30, 90, 365)
MAX_DURATION_DAYS = 3650  # 10 years — generous ceiling against fat-finger entry, mirrors no hard business rule existing elsewhere
