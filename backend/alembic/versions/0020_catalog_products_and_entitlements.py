"""Unified Learning Catalog / Grade Subscriptions — Phase 1: catalog
products and entitlements data model.

Fully additive. No existing table's column, constraint, or data is
dropped, renamed, retyped, or backfilled. Adds exactly TWO new tables.
Every existing `plans`/`subscriptions`/`payments`/`transactions` row
(and every row in every other existing table) is untouched by this
migration — confirmed by this migration containing no ALTER/DROP
against any pre-existing table other than one additive, nullable
`op.add_column`... actually no — see below, `payments` itself is NOT
altered either; `entitlements.payment_id` is a new column on the NEW
`entitlements` table referencing `payments.id`, not a change to
`payments` itself.

catalog_products (new table)
  The purchasable unit. `product_type` ∈ {'grade_subscription',
  'mock_test', 'course'}. Exactly one of grade_id/subject_id is set,
  matching product_type — enforced by
  ck_catalog_products_ref_matches_type. grade_id/subject_id each carry
  a plain UNIQUE constraint (not composite with product_type) —
  Postgres allows multiple NULLs, so this only constrains the rows that
  set that column, i.e. exactly the rows of the matching type. This is
  what makes "one catalog product per grade" / "one catalog product per
  subject/exam-direction" a DB-level guarantee, not just an
  application-level convention — see app/modules/catalog/README.md
  "Known simplification" for what this trades off.

  REVISED for the Subject-Specific and Exam-Specific Mock Test
  Entitlements feature: a mock_test product now keys on subject_id
  (the subject or exam direction — e.g. Physics, or IELTS, both just
  rows in the existing `subjects` table), not a single test_id. This
  grants access to every published mock test under that direction, per
  that feature's spec §1, rather than unlocking one test at a time.
  This file was edited in place (not superseded by a later migration)
  because, at the time of this edit, 0020 had never been applied to
  any database in this project's own environment — see this project's
  own standing rule that the sandbox here never runs real migrations
  against a live Postgres (no Docker daemon available).

entitlements (new table)
  The access-check table. Ties a user to one catalog_products row,
  with a source (purchase vs admin_grant — spec §4/§7's "recorded
  separately" requirement), an optional link back to the payments row
  that created it (payment_id, nullable, NULL for admin grants), and a
  status (active/expired/revoked). A partial UNIQUE index enforces at
  most one ACTIVE entitlement per (user_id, product_id) at a time,
  without blocking a user from ever re-purchasing the same product
  after a prior entitlement expired or was revoked (those rows keep
  their own status, preserving history — spec §5's "preserve
  historical payment and subscription records").

No existing router, service, or endpoint reads either new table in
this migration — see app/modules/catalog/README.md and
app/modules/entitlements/README.md for exactly what is and is not
wired up yet. This migration's blast radius is therefore zero for any
currently-running behavior: every existing endpoint returns exactly
what it returned before this migration runs.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_type", sa.String(30), nullable=False),
        sa.Column("grade_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grades.id"), nullable=True, unique=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=True, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "product_type IN ('grade_subscription', 'mock_test', 'course')",
            name="ck_catalog_products_product_type_allowed",
        ),
        sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_catalog_products_status_allowed"),
        sa.CheckConstraint(
            "("
            "  (product_type = 'grade_subscription' AND grade_id IS NOT NULL AND subject_id IS NULL)"
            "  OR (product_type = 'mock_test' AND subject_id IS NOT NULL AND grade_id IS NULL)"
            "  OR (product_type = 'course' AND grade_id IS NULL AND subject_id IS NULL)"
            ")",
            name="ck_catalog_products_ref_matches_type",
        ),
        sa.CheckConstraint("price >= 0", name="ck_catalog_products_price_non_negative"),
        sa.CheckConstraint("duration_days IS NULL OR duration_days > 0", name="ck_catalog_products_duration_positive"),
    )
    op.create_index("ix_catalog_products_product_type", "catalog_products", ["product_type"])
    op.create_index("ix_catalog_products_status", "catalog_products", ["status"])

    op.create_table(
        "entitlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("catalog_products.id"), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("source IN ('purchase', 'admin_grant')", name="ck_entitlements_source_allowed"),
        sa.CheckConstraint("status IN ('active', 'expired', 'revoked')", name="ck_entitlements_status_allowed"),
        sa.CheckConstraint(
            "(source = 'admin_grant' AND granted_by IS NOT NULL) OR (source = 'purchase' AND granted_by IS NULL)",
            name="ck_entitlements_admin_grant_has_granter",
        ),
        sa.CheckConstraint("end_date IS NULL OR end_date > start_date", name="ck_entitlements_end_after_start"),
    )
    op.create_index("ix_entitlements_user_id", "entitlements", ["user_id"])
    op.create_index("ix_entitlements_product_id", "entitlements", ["product_id"])
    op.create_index(
        "uq_entitlements_active_user_product",
        "entitlements",
        ["user_id", "product_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_entitlements_active_user_product", table_name="entitlements")
    op.drop_index("ix_entitlements_product_id", table_name="entitlements")
    op.drop_index("ix_entitlements_user_id", table_name="entitlements")
    op.drop_table("entitlements")

    op.drop_index("ix_catalog_products_status", table_name="catalog_products")
    op.drop_index("ix_catalog_products_product_type", table_name="catalog_products")
    op.drop_table("catalog_products")
