"""Investment positions, contribution links and net worth snapshots.

Revision ID: 0005_investments
Revises: 0004_budgets
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_investments"
down_revision = "0004_budgets"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "investment_contributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        *timestamps(),
    )
    op.create_index("ix_investment_contributions_user", "investment_contributions", ["user_id"])
    op.create_table(
        "investment_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("symbol", sa.String(32)),
        sa.Column("units", sa.Numeric(24, 8), nullable=False),
        sa.Column("cost_basis", sa.Numeric(18, 2), nullable=False),
        sa.Column("market_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("valued_on", sa.Date(), nullable=False),
        sa.CheckConstraint("units > 0"), sa.CheckConstraint("cost_basis >= 0"),
        sa.CheckConstraint("market_value >= 0"), *timestamps(),
    )
    op.create_index("ix_investment_positions_user_account", "investment_positions", ["user_id", "account_id"])
    op.create_table(
        "net_worth_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("assets", sa.Numeric(18, 2), nullable=False),
        sa.Column("liabilities", sa.Numeric(18, 2), nullable=False),
        sa.Column("net_worth", sa.Numeric(18, 2), nullable=False),
        sa.UniqueConstraint("user_id", "date", "currency", name="uq_net_worth_user_date_currency"),
        *timestamps(),
    )
    op.create_index("ix_net_worth_snapshots_user_date", "net_worth_snapshots", ["user_id", "date"])


def downgrade() -> None:
    for table in ("net_worth_snapshots", "investment_positions", "investment_contributions"):
        op.drop_table(table)
