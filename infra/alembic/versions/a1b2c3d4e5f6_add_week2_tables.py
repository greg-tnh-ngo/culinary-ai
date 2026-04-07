"""add week2 tables

Revision ID: a1b2c3d4e5f6
Revises: 7ed9a1b46146
Create Date: 2026-04-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "7ed9a1b46146"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("stream", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="IDEA"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "scripts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("videos.id"), nullable=False),
        sa.Column("variant", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("verification", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("script_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("scripts.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("quoted", sa.Text(), nullable=True),
        sa.Column("accessed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("avg_price_per_unit", sa.Numeric(), nullable=True),
        sa.Column("current_qty", sa.Numeric(), server_default="0", nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
    )

    op.create_table(
        "recipes",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.SmallInteger(), nullable=True),
        sa.Column("time_required_minutes", sa.SmallInteger(), nullable=True),
        sa.Column("stream", sa.Text(), nullable=True),
    )

    op.create_table(
        "recipe_ingredients",
        sa.Column("recipe_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("ingredients.id"), nullable=False),
        sa.Column("qty", sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint("recipe_id", "ingredient_id"),
    )

    op.create_table(
        "ledger_weeks",
        sa.Column("week_id", sa.Date(), primary_key=True),
        sa.Column("budget_limit", sa.Numeric(), server_default="100", nullable=False),
        sa.Column("planned_spend", sa.Numeric(), server_default="0", nullable=False),
        sa.Column("actual_spend", sa.Numeric(), server_default="0", nullable=False),
    )

    op.create_table(
        "purchases",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("store", sa.Text(), nullable=True),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total", sa.Numeric(), nullable=True),
    )


def downgrade():
    op.drop_table("recipe_ingredients")
    op.drop_table("sources")
    op.drop_table("scripts")
    op.drop_table("videos")
    op.drop_table("purchases")
    op.drop_table("ledger_weeks")
    op.drop_table("recipes")
    op.drop_table("ingredients")
