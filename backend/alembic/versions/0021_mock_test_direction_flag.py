"""Subject-Specific and Exam-Specific Mock Test Entitlements — adds the
`is_mock_test` flag to `tests`.

Fully additive. No existing column, constraint, or row value is
dropped/retyped. One new column with a NOT-NULL server default of
`false`, so every one of the pre-existing rows in `tests` gets
`is_mock_test = false` automatically — none of them is silently
reinterpreted as a mock test (spec: "Do not silently assign
uncategorized tests to an unrelated direction"). An admin must
explicitly flip a test to `is_mock_test = true`, and the app layer
(TestService._validate_mock_test_consistency) plus the CHECK constraint
below both require `subject_id` to already be set before that is
allowed — "handle existing mock tests whose subject or direction is
missing" is satisfied by refusing the categorization at write time,
not by guessing a direction after the fact for old rows.

Why `subject_id` (not a new `direction_id`/`exam_direction` column):
`subjects` is already a fully generic lookup (name/icon/color only, no
school-only restriction) and `Test.subject_id` already exists as a
nullable FK to it — reusing it for IELTS/SAT/GRE rows (as new Subject
rows an admin creates, exactly like 'Fizika'/'Matematika') avoids
hardcoding any category name anywhere in code, per the spec's explicit
"these are examples, not a requirement to hardcode these categories."

ck_tests_mock_test_requires_subject mirrors the service-layer check so
a direct DB write (or a future code path that forgets to call the
service) can never leave an ambiguous mock-test-with-no-direction row.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tests",
        sa.Column("is_mock_test", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_tests_mock_test_requires_subject",
        "tests",
        "is_mock_test = false OR subject_id IS NOT NULL",
    )
    op.create_index("ix_tests_is_mock_test", "tests", ["is_mock_test"])


def downgrade() -> None:
    op.drop_index("ix_tests_is_mock_test", table_name="tests")
    op.drop_constraint("ck_tests_mock_test_requires_subject", "tests", type_="check")
    op.drop_column("tests", "is_mock_test")
