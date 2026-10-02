"""Saved financial simulation scenarios.

Revision ID: 0007_scenarios
Revises: 0006_imports
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_scenarios"
down_revision = "0006_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scenarios_user", "scenarios", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_scenarios_user", table_name="scenarios")
    op.drop_table("scenarios")
