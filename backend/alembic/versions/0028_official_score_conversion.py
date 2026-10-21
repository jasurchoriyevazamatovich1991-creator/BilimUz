"""Task 7 — official-source-based score conversion (IELTS, Digital SAT, GRE).

Additive only; no data is rewritten and no official conversion data is
inserted. Every existing row keeps its meaning:

- tests.ielts_module                     'academic' | 'general_training' | NULL (CHECK)
- score_conversion_tables.conversion_type
                                         NOT NULL, server default 'unverified' — every
                                         table created before this migration had no
                                         recorded source, so it is labelled unverified
  + test_form, source_url, source_title, source_version, source_verified_at (nullable)
  + method CHECK widened to also allow 'range' (lower/upper per raw score)
- result_sections.score_basis / scaled_score_lower / scaled_score_upper /
  score_source_key (nullable) — NULL on all existing rows
- results.overall_basis / overall_score_lower / overall_score_upper (nullable)

Downgrade drops the new columns. It refuses (CHECK violation) if any
'range' table exists, rather than silently deleting published tables;
remove those tables explicitly first if a downgrade is really needed.

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tests", sa.Column("ielts_module", sa.String(20), nullable=True))
    op.create_check_constraint(
        "ck_tests_ielts_module_allowed", "tests",
        "ielts_module IS NULL OR ielts_module IN ('academic', 'general_training')",
    )

    op.add_column("score_conversion_tables", sa.Column("conversion_type", sa.String(30), nullable=False, server_default="unverified"))
    op.create_check_constraint(
        "ck_score_conversion_tables_conversion_type", "score_conversion_tables",
        "conversion_type IN ('official_practice_test', 'estimate', 'unverified')",
    )
    op.add_column("score_conversion_tables", sa.Column("test_form", sa.String(60), nullable=True))
    op.add_column("score_conversion_tables", sa.Column("source_url", sa.String(500), nullable=True))
    op.add_column("score_conversion_tables", sa.Column("source_title", sa.String(300), nullable=True))
    op.add_column("score_conversion_tables", sa.Column("source_version", sa.String(100), nullable=True))
    op.add_column("score_conversion_tables", sa.Column("source_verified_at", sa.Date(), nullable=True))
    op.drop_constraint("ck_score_conversion_tables_method", "score_conversion_tables", type_="check")
    op.create_check_constraint(
        "ck_score_conversion_tables_method", "score_conversion_tables", "method IN ('exact', 'linear', 'range')",
    )

    op.add_column("result_sections", sa.Column("score_basis", sa.String(30), nullable=True))
    op.add_column("result_sections", sa.Column("scaled_score_lower", sa.Numeric(8, 2), nullable=True))
    op.add_column("result_sections", sa.Column("scaled_score_upper", sa.Numeric(8, 2), nullable=True))
    op.add_column("result_sections", sa.Column("score_source_key", sa.String(80), nullable=True))

    op.add_column("results", sa.Column("overall_basis", sa.String(30), nullable=True))
    op.add_column("results", sa.Column("overall_score_lower", sa.Numeric(6, 1), nullable=True))
    op.add_column("results", sa.Column("overall_score_upper", sa.Numeric(6, 1), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "overall_score_upper")
    op.drop_column("results", "overall_score_lower")
    op.drop_column("results", "overall_basis")
    op.drop_column("result_sections", "score_source_key")
    op.drop_column("result_sections", "scaled_score_upper")
    op.drop_column("result_sections", "scaled_score_lower")
    op.drop_column("result_sections", "score_basis")
    op.drop_constraint("ck_score_conversion_tables_method", "score_conversion_tables", type_="check")
    op.create_check_constraint(
        "ck_score_conversion_tables_method", "score_conversion_tables", "method IN ('exact', 'linear')",
    )
    op.drop_column("score_conversion_tables", "source_verified_at")
    op.drop_column("score_conversion_tables", "source_version")
    op.drop_column("score_conversion_tables", "source_title")
    op.drop_column("score_conversion_tables", "source_url")
    op.drop_column("score_conversion_tables", "test_form")
    op.drop_constraint("ck_score_conversion_tables_conversion_type", "score_conversion_tables", type_="check")
    op.drop_column("score_conversion_tables", "conversion_type")
    op.drop_constraint("ck_tests_ielts_module_allowed", "tests", type_="check")
    op.drop_column("tests", "ielts_module")
