"""create pipeline_runs

Revision ID: 7ed9a1b46146
Revises:
Create Date: 2025-10-14 00:19:36.193321
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "7ed9a1b46146"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("idea", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scripts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("shoot_card", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

def downgrade():
    op.drop_table("pipeline_runs")
