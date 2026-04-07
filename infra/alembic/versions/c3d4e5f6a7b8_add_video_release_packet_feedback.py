"""add release_packet and feedback to videos

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("videos", sa.Column("release_packet", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("videos", sa.Column("feedback", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("videos", "feedback")
    op.drop_column("videos", "release_packet")
