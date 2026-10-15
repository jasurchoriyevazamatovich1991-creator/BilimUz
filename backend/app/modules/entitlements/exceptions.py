"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class EntitlementNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "ENTITLEMENT_NOT_FOUND"


class DuplicateActiveEntitlementException(AppException):
    """Raised when the user already holds an active entitlement for
    this exact product — the partial unique index on (user_id,
    product_id) WHERE status='active' (see models.py) is the DB-level
    backstop for this same rule."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "DUPLICATE_ACTIVE_ENTITLEMENT"


class ProductNotPurchasableException(AppException):
    """Raised when a purchase-sourced entitlement is attempted against
    a product that isn't published (draft/archived)."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "PRODUCT_NOT_PURCHASABLE"


class AdminGrantRequiresGranterException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "ADMIN_GRANT_REQUIRES_GRANTER"


# --- Admin Management of Mock Test Entitlements (Task D) ---

class TargetUserNotFoundException(AppException):
    """Raised when an admin grants/lists entitlements for a user_id that
    doesn't exist. Named "Target" (not reusing users.exceptions.
    UserNotFoundException) to keep this module's exceptions
    self-contained — see roles/repository.py's documented precedent for
    why a read-only cross-module reference (here: checking a user_id
    exists) is fine without importing the other module's exception
    types too."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "TARGET_USER_NOT_FOUND"


class ProductNotMockTestException(AppException):
    """Raised when an admin-grant/extend request targets a
    catalog_products row that isn't product_type='mock_test' — this
    admin surface is scoped to Mock Test Entitlements only (spec title);
    grade subscriptions and courses are managed through other phases
    even though they share the same Entitlement table."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "PRODUCT_NOT_MOCK_TEST"
