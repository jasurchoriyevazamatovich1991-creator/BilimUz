"""
CatalogProduct ORM model — the purchasable unit behind the Unified
Learning Catalog / Grade Subscriptions plan. New table, fully additive
(migration 0020) — no existing table's columns are touched.

Deliberately generic across three product types (spec §4 — "Grade
subscriptions, mock tests, and exam-preparation courses are independent
products"):
  - grade_subscription -> grade_id (FK grades.id) is set, subject_id is NULL
  - mock_test          -> subject_id (FK subjects.id) is set, grade_id is NULL.
                          Revised by the Mock Test Entitlements feature:
                          a mock_test product grants access to EVERY
                          published mock test under one subject/exam
                          direction (e.g. all published Physics mock
                          tests, or all published IELTS mock tests) —
                          not a single test. subject_id is reused
                          exactly as grade_id is reused for
                          grade_subscription: `subjects` is already a
                          fully generic lookup (name/icon/color only),
                          so an exam direction like IELTS/SAT/GRE is
                          just another Subject row an admin creates,
                          never a hardcoded category name anywhere in
                          code.
  - course             -> neither ref is set (IELTS/SAT/GRE preparation
                           *course* content assignment is explicitly
                           deferred — see this module's README
                           "Deferred to a later phase"; a 'course'
                           product today is pricing/catalog metadata
                           only. This is intentionally separate from a
                           mock_test product for the same direction —
                           spec: "access to IELTS mock tests does not
                           automatically grant access to an IELTS
                           preparation course" — they are different
                           product_type rows even when they share a
                           conceptual "IELTS" name.)

The CHECK constraint below enforces this exclusivity at the DB level,
not just in the service layer — a row that claims to be a
grade_subscription but has no grade_id (or has a subject_id) can never
be inserted, regardless of which code path tries.

Each of grade_id/subject_id also carries a plain UNIQUE constraint (NOT
a composite with product_type) — Postgres treats multiple NULLs as
distinct, so this only ever constrains the rows that actually set that
column, which are exactly the rows of the matching product_type. This
is what gives "a Grade 3 subscription must not grant access to Grade
2/4" AND "a Physics entitlement must not grant access to Mathematics"
their DB-level half: a grade (or a subject, for mock tests) can only
ever have ONE catalog_products row of that type, so there is no
row-selection ambiguity for the entitlement check to get wrong. See
this module's README for the known simplification this implies
(archiving a grade's or subject's product currently blocks creating a
replacement row for it — reusing the existing row via PATCH is the
intended workaround until a future phase revisits this).

status is its own draft/published/archived enum (constants.py), NOT the
shared StatusMixin's generic active/inactive — mirrors the one existing
precedent for a real publication-status enum in this codebase,
tests.models.TestStatus, per StatusMixin's own documented rule ("Tables
that already define their own domain-specific status enum should NOT
use this mixin").
"""
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.mixins import AuditMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.base import Base
from app.modules.catalog.constants import (
    ALLOWED_PRODUCT_STATUS_VALUES,
    ALLOWED_PRODUCT_TYPES,
    PRODUCT_STATUS_DRAFT,
    PRODUCT_TYPE_GRADE_SUBSCRIPTION,
    PRODUCT_TYPE_MOCK_TEST,
)


class CatalogProduct(Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditMixin):
    __tablename__ = "catalog_products"
    __table_args__ = (
        CheckConstraint(
            "product_type IN ('grade_subscription', 'mock_test', 'course')",
            name="ck_catalog_products_product_type_allowed",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_catalog_products_status_allowed",
        ),
        CheckConstraint(
            "("
            "  (product_type = 'grade_subscription' AND grade_id IS NOT NULL AND subject_id IS NULL)"
            "  OR (product_type = 'mock_test' AND subject_id IS NOT NULL AND grade_id IS NULL)"
            "  OR (product_type = 'course' AND grade_id IS NULL AND subject_id IS NULL)"
            ")",
            name="ck_catalog_products_ref_matches_type",
        ),
        CheckConstraint("price >= 0", name="ck_catalog_products_price_non_negative"),
        CheckConstraint("duration_days IS NULL OR duration_days > 0", name="ck_catalog_products_duration_positive"),
    )

    product_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Exactly one of these two is set, enforced by ck_catalog_products_ref_matches_type
    # above — see the class docstring for why 'course' sets neither.
    grade_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grades.id"), nullable=True, unique=True,
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True, unique=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    # NULL = no expiry (e.g. a lifetime mock-test unlock). Non-NULL is
    # the number of days an Entitlement created from this product lasts.
    duration_days: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PRODUCT_STATUS_DRAFT)


# Re-exported here so callers that only need the literal values don't
# have to reach into constants.py directly — matches how tests.models
# exposes DifficultyLevel/TestStatus as StrEnums alongside the model.
__all__ = ["CatalogProduct", "ALLOWED_PRODUCT_TYPES", "ALLOWED_PRODUCT_STATUS_VALUES",
           "PRODUCT_TYPE_GRADE_SUBSCRIPTION", "PRODUCT_TYPE_MOCK_TEST"]
