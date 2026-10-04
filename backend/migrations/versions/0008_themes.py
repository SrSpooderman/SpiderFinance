"""Add a per-user color theme.

Revision ID: 0008_themes
Revises: 0007_scenarios
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_themes"
down_revision = "0007_scenarios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("theme", sa.String(20), nullable=False, server_default="light-teal"))


def downgrade() -> None:
    op.drop_column("user_settings", "theme")
