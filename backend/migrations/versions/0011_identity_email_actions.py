"""Email ownership and one-time identity actions.

Revision ID: 0011_identity_email_actions
Revises: 0010_password_sessions
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_identity_email_actions"
down_revision = "0010_password_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "identity_action_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_identity_action_tokens_user_id", "identity_action_tokens", ["user_id"])
    op.create_index("ix_identity_action_tokens_purpose", "identity_action_tokens", ["purpose"])
    op.create_table(
        "identity_mail_throttles",
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("identity_mail_throttles")
    op.drop_index("ix_identity_action_tokens_purpose", table_name="identity_action_tokens")
    op.drop_index("ix_identity_action_tokens_user_id", table_name="identity_action_tokens")
    op.drop_table("identity_action_tokens")
    op.drop_column("users", "email_verified_at")
