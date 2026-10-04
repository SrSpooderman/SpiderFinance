"""Store profile photos in the database.

Revision ID: 0009_profile_photos
Revises: 0008_themes
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_profile_photos"
down_revision = "0008_themes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profile_photos",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_profile_photos")
