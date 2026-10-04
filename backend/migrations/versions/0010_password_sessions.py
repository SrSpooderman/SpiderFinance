"""Invalidate user sessions after a password change or reset.

Revision ID: 0010_password_sessions
Revises: 0009_profile_photos
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_password_sessions"
down_revision = "0009_profile_photos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "auth_version")
