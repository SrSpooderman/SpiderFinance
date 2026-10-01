"""Income, obligations and debt planning.

Revision ID: 0002_planning
Revises: 0001_foundations
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_planning"
down_revision = "0001_foundations"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def common() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "income_sources", *common(),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("day_rule", sa.String(32), nullable=False),
        sa.Column("day_of_month", sa.Integer()),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.CheckConstraint("amount > 0"), *timestamps(),
    )
    op.create_index("ix_income_sources_user", "income_sources", ["user_id"])
    op.create_table(
        "recurring_expenses", *common(),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="RESTRICT")),
        sa.Column("frequency", sa.String(16), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("amount > 0"), *timestamps(),
    )
    op.create_index("ix_recurring_expenses_user", "recurring_expenses", ["user_id"])
    op.create_table(
        "scheduled_expenses", *common(),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="RESTRICT")),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="RESTRICT"), unique=True),
        sa.CheckConstraint("amount > 0"), *timestamps(),
    )
    op.create_index("ix_scheduled_expenses_user_due", "scheduled_expenses", ["user_id", "due_date"])
    op.create_table(
        "debts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("principal", sa.Numeric(18, 2), nullable=False),
        sa.Column("installment_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("due_day", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("principal > 0"), sa.CheckConstraint("installment_amount > 0"), *timestamps(),
    )
    op.create_index("ix_debts_user", "debts", ["user_id"])
    op.create_table(
        "income_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("income_sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.UniqueConstraint("source_id", "due_date"), *timestamps(),
    )
    op.create_table(
        "recurring_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expense_id", sa.Integer(), sa.ForeignKey("recurring_expenses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.UniqueConstraint("expense_id", "due_date"), *timestamps(),
    )
    op.create_table(
        "debt_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("debt_id", sa.Integer(), sa.ForeignKey("debts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        *timestamps(),
    )


def downgrade() -> None:
    for table in ("debt_payments", "recurring_payments", "income_receipts", "debts", "scheduled_expenses", "recurring_expenses", "income_sources"):
        op.drop_table(table)
