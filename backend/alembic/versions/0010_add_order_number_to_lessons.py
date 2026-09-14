"""Add order_number to lessons (Sprint 38 — Lesson Ordering)

Approved architecture: mirrors Topic.order_number exactly (Integer,
NOT NULL, default 0) — same pattern, one level deeper in the hierarchy
(Subject/Grade -> Topic -> Lesson). Unlike Topic (which has no DB-level
uniqueness on order_number), Lesson additionally gets a real
UNIQUE(topic_id, order_number) constraint — this sprint's explicit
requirement — since a Topic's lessons need a genuinely deterministic,
gap-free-by-construction viewing order for students, not just an
advisory sort hint.

BACKFILL (safe, deterministic): existing lessons are numbered 0, 1,
2, ... within each topic_id, ordered by created_at ASC, id ASC —
oldest-first, matching "the order lessons were originally added" as
the most sensible deterministic default when no explicit order existed
before. `id ASC` is a stable tie-breaker for the theoretical case of
two lessons in the same topic sharing an identical created_at
timestamp — created_at alone cannot guarantee a fully deterministic
ORDER BY for ROW_NUMBER(), but the primary key always can. This runs
entirely in SQL (a single UPDATE with a window function) so it is safe
and fast even on a large lessons table, and requires no Python/ORM
round-trip.

The UNIQUE constraint is added in a SEPARATE step, AFTER the backfill
completes, so a table with genuinely duplicate (topic_id, order_number)
pairs before this migration (default=0 for every lesson) is guaranteed
to satisfy the constraint by the time it's enforced.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lessons", sa.Column("order_number", sa.Integer(), nullable=False, server_default="0"))

    # Deterministic backfill: number existing lessons 0, 1, 2... within
    # each topic, oldest-created first. `id ASC` is a stable tie-breaker
    # for the (theoretically possible) case of two lessons in the same
    # topic sharing an identical created_at timestamp — ROW_NUMBER()
    # requires a fully deterministic ORDER BY to guarantee reproducible
    # results, and created_at alone cannot guarantee that.
    op.execute("""
        UPDATE lessons
        SET order_number = sub.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY topic_id ORDER BY created_at ASC, id ASC) - 1 AS rn
            FROM lessons
        ) AS sub
        WHERE lessons.id = sub.id
    """)

    op.create_unique_constraint("uq_lessons_topic_id_order_number", "lessons", ["topic_id", "order_number"])
    op.alter_column("lessons", "order_number", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_lessons_topic_id_order_number", "lessons", type_="unique")
    op.drop_column("lessons", "order_number")
