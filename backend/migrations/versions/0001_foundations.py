"""Initial users, accounts, categories and movements.

Revision ID: 0001_foundations
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_foundations"
down_revision = None
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False), *timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "user_settings", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("locale", sa.String(32), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
    )
    op.create_table(
        "accounts", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("type", sa.String(32), nullable=False),
        sa.Column("institution", sa.String(120)), sa.Column("initial_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text()), *timestamps(),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])
    op.create_table(
        "categories", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="RESTRICT")),
        sa.Column("name", sa.String(100), nullable=False), *timestamps(),
        sa.UniqueConstraint("user_id", "parent_id", "name", name="uq_category_sibling_name"),
    )
    op.create_index("ix_categories_user_id", "categories", ["user_id"])
    op.create_table(
        "transactions", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False), sa.Column("type", sa.String(16), nullable=False),
        sa.Column("source_account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT")),
        sa.Column("destination_account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT")),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="RESTRICT")),
        sa.Column("concept", sa.String(240), nullable=False), sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("payment_method", sa.String(50)), sa.Column("is_fixed", sa.Boolean(), nullable=False),
        sa.Column("is_necessary", sa.Boolean(), nullable=False), sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("reconciliation", sa.Boolean(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_transaction_amount_positive"), *timestamps(),
    )
    op.create_index("ix_transactions_user_date", "transactions", ["user_id", "date"])
    op.create_index("ix_transactions_source", "transactions", ["source_account_id"])
    op.create_index("ix_transactions_destination", "transactions", ["destination_account_id"])
    op.create_index("ix_transactions_category", "transactions", ["category_id"])


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("categories")
    op.drop_table("accounts")
    op.drop_table("user_settings")
    op.drop_table("users")
