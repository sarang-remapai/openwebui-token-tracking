"""rename daily_credit_limit to monthly_credit_limit

Revision ID: f1a2b3c4d5e6
Revises: a118dd7f6b7f
Create Date: 2025-01-20 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "a118dd7f6b7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name, column_name):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Rename the column from daily_credit_limit to monthly_credit_limit
    # Only rename if daily_credit_limit exists (for existing databases)
    # For fresh installs, the column will already be named monthly_credit_limit
    if column_exists("token_tracking_sponsored_allowance", "daily_credit_limit"):
        with op.batch_alter_table("token_tracking_sponsored_allowance") as batch_op:
            batch_op.alter_column(
                "daily_credit_limit",
                new_column_name="monthly_credit_limit",
            )


def downgrade() -> None:
    # Rename the column back from monthly_credit_limit to daily_credit_limit
    # Only rename if monthly_credit_limit exists
    if column_exists("token_tracking_sponsored_allowance", "monthly_credit_limit"):
        with op.batch_alter_table("token_tracking_sponsored_allowance") as batch_op:
            batch_op.alter_column(
                "monthly_credit_limit",
                new_column_name="daily_credit_limit",
            )

