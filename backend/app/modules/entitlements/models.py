"""
Entitlement ORM model — the actual access-check table. New table, fully
additive (migration 0020) — no existing table's columns are touched.

Why a new table instead of reusing payments.Subscription: confirmed by
direct audit that Subscription (user_id, plan_id, start/end, status) is
never read by any module outside `payments` itself, and Plan has no
link to any catalog entity at all (no grade_id/product reference) —
there is nothing in the existing schema an access check could key off
of. Entitlement is the thing that ties "this user" to "this specific
catalog_products row" in a way a future enforcement phase can actually
query. Subscription/Plan/Payment/Transaction are left completely
untouched — existing payment history is preserved exactly as-is.

source distinguishes a verified purchase from an administrator's manual
grant (spec §4 — "Administrator-granted access must be recorded
separately from paid access" and §7 — "See whether access came from a
verified purchase or manual administrative grant"). granted_by is
required when source='admin_grant' (ck_entitlements_admin_grant_has_granter
below) and must be NULL for a purchase — nobody "grants" a purchase.

payment_id optionally links back to the payments.payments row that
produced this entitlement (NULL for admin grants) — this is how a
reconciliation view (a later phase) will join "this access" back to
"this payment" without duplicating any payment data here.

No enforcement/"does this grant access right now" logic reads this
table from any content endpoint yet in this phase — see this module's
README. EntitlementService.has_active_grade_entitlement() exists and is
unit-tested, but nothing calls it from a router yet; wiring it in is
explicitly the next phase (see the audit's own phased plan), not done
here, so no previously-public endpoint silently becomes gated by this
migration landing.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from app.modules.entitlements.constants import STATUS_ACTIVE


class Entitlement(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin):
    __tablename__ = "entitlements"
    __table_args__ = (
        CheckConstraint("source IN ('purchase', 'admin_grant')", name="ck_entitlements_source_allowed"),
        CheckConstraint("status IN ('active', 'expired', 'revoked')", name="ck_entitlements_status_allowed"),
        CheckConstraint(
            "(source = 'admin_grant' AND granted_by IS NOT NULL) OR (source = 'purchase' AND granted_by IS NULL)",
            name="ck_entitlements_admin_grant_has_granter",
        ),
        CheckConstraint("end_date IS NULL OR end_date > start_date", name="ck_entitlements_end_after_start"),
        # Partial unique index — only one ACTIVE entitlement per
        # (user_id, product_id) at a time. A revoked/expired row never
        # blocks a fresh purchase/grant of the same product (e.g.
        # resubscribing after expiry creates a new row rather than
        # reactivating the old one, which keeps the history of each
        # period intact — spec §5 "preserve historical... records").
        Index(
            "uq_entitlements_active_user_product",
            "user_id", "product_id",
            unique=True,
            postgresql_where="status = 'active'",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("catalog_products.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_ACTIVE)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL = no expiry, mirrors CatalogProduct.duration_days=NULL.
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Added for Admin Management of Mock Test Entitlements (migration
    # 0022, additive/nullable) — free-text justification an admin can
    # attach to a grant/extend/revoke (spec §3 — "Record ... reason
    # where supported by the existing schema"). NULL for every
    # pre-existing row and for purchase-sourced entitlements, which have
    # no admin behind them to give a reason.
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
