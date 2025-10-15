"""create pipeline_runs

Revision ID: 7ed9a1b46146
Revises: 
Create Date: 2025-10-14 00:19:36.193321
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7ed9a1b46146'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the pipeline_runs table."""
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("idea", postgresql.JSONB),
        sa.Column("scripts", postgresql.JSONB),
        sa.Column("shoot_card", postgresql.JSONB),
    )


def downgrade() -> None:
    """Drop the pipeline_runs table if rolling back."""
    op.drop_table("pipeline_runs")
