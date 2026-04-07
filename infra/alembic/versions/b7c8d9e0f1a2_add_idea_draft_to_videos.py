"""add idea_draft to videos

Revision ID: b7c8d9e0f1a2
Revises: a8b9c0d1e2f3
Create Date: 2026-04-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b7c8d9e0f1a2"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "videos",
        sa.Column("idea_draft", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade():
    op.drop_column("videos", "idea_draft")
