"""Recurring monthly and salary cycle budgets.

Revision ID: 0004_budgets
Revises: 0003_savings
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_budgets"
down_revision = "0003_savings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="RESTRICT")),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0"),
    )
    op.create_index("ix_budgets_user", "budgets", ["user_id"])


def downgrade() -> None:
    op.drop_table("budgets")
