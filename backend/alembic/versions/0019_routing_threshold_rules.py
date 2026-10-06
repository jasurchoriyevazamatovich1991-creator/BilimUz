"""Sprint 75 — Live Adaptive Routing Engine: persistent threshold config.

Fully additive. No existing column, table, or constraint is dropped,
renamed, or retyped. Adds exactly ONE new table.

WHY THIS MIGRATION IS NEEDED (Phase 3 persistence decision):

Sprint 75's audit confirmed that `PerformanceThresholdRoutingStrategy`
(attempts/adaptive_routing.py, Sprint 49) has existed since Sprint 49 as
a pure, unit-tested strategy, but requires a caller-supplied
`rules_by_group: dict[str, list[PerformanceThresholdRule(min_ratio,
variant)]]` at construction time. No existing column anywhere in the
schema stores this: `ExamModule.routing_group`/`routing_variant` are
plain nullable labels (Sprint 48) with no numeric threshold semantics,
and `ExamModule.difficulty_tier` (Sprint 46) is an unconstrained,
unordered free-text label — none of them can supply a `min_ratio`
without this sprint inventing an arbitrary ordering/semantics for those
existing string fields, which the Sprint 75 brief explicitly forbids
("Do NOT invent... do NOT hardcode specific difficulty names"). Per
Phase 3's explicit preference order, OPTION A (no migration) was
therefore ruled out as unsafe/impossible without inventing data that
isn't there — OPTION B (minimal migration) is the only honest path.

routing_threshold_rules (new table)
  One row = one (routing_group, min_ratio -> variant) rule, scoped to a
  single Test via test_id. Scoping by test_id (rather than a bare
  routing_group string with no test scope) is a deliberate, additive
  safety property beyond what PerformanceThresholdRoutingStrategy's own
  pure-Python constructor requires: it guarantees a rule written for one
  Test's "verbal" routing_group can never be loaded by, or leak into,
  the routing decision for a different Test that happens to reuse the
  same routing_group name — see RoutingThresholdRuleRepository
  .get_rules_by_group_for_test(), the only reader.

  UNIQUE(test_id, routing_group, min_ratio) prevents an ambiguous
  configuration (two different variants claiming the exact same
  threshold within the same test+group), which
  PerformanceThresholdRoutingStrategy's own `max(matching_rules, key=...)`
  tie-break would otherwise resolve by undefined list order.

  min_ratio is NUMERIC(5,4) with a CHECK (min_ratio >= 0 AND
  min_ratio <= 1) — mirrors ModulePerformance's own ratio domain
  (correct_count / total_count, Sprint 49) exactly; no new semantics
  invented.

No admin UI or HTTP endpoint is added for this table in Sprint 75 (the
brief's explicit scope: "no new routing admin UI unless strictly
required by the existing architecture" — it is not required to prove
the execution-layer wiring; Sprint 75's integration tests populate rows
directly via the ORM, the same way Sprint 74's own tests exercised
ExamSection/ExamModule before any admin UI existed for them). This means
the table has ZERO rows in every pre-existing exam today, which is
exactly what makes Sprint 75 backward-compatible by construction: no
`routing_group` can ever be "configured" until a future sprint adds a
way to write rows here, so every existing exam keeps using
SequentialRoutingStrategy, completely unchanged (see
ModuleExecutionService._select_routing_strategy()).

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "routing_threshold_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("routing_group", sa.String(50), nullable=False),
        sa.Column("min_ratio", sa.Numeric(5, 4), nullable=False),
        sa.Column("variant", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("test_id", "routing_group", "min_ratio", name="uq_routing_threshold_rules_test_group_ratio"),
        sa.CheckConstraint("min_ratio >= 0 AND min_ratio <= 1", name="ck_routing_threshold_rules_min_ratio_range"),
    )
    op.create_index("ix_routing_threshold_rules_test_id", "routing_threshold_rules", ["test_id"])


def downgrade() -> None:
    op.drop_index("ix_routing_threshold_rules_test_id", table_name="routing_threshold_rules")
    op.drop_table("routing_threshold_rules")
