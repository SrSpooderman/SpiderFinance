"""Goals, virtual reservations and savings rules.

Revision ID: 0003_savings
Revises: 0002_planning
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_savings"
down_revision = "0002_planning"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "savings_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("target_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("target_amount > 0"), *timestamps(),
    )
    op.create_index("ix_savings_goals_user", "savings_goals", ["user_id"])
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("savings_goals.id", ondelete="RESTRICT")),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.UniqueConstraint("user_id", "account_id", "goal_id", name="uq_reservation_account_goal"),
        sa.CheckConstraint("amount >= 0"), *timestamps(),
    )
    op.create_index("ix_reservations_user", "reservations", ["user_id"])
    op.create_table(
        "goal_contributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("savings_goals.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("amount <> 0"), *timestamps(),
    )
    op.create_index("ix_goal_contributions_user_date", "goal_contributions", ["user_id", "date"])
    op.create_table(
        "savings_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("income_source_id", sa.Integer(), sa.ForeignKey("income_sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("value", sa.Numeric(18, 2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("value > 0"), *timestamps(),
    )
    op.create_index("ix_savings_rules_user", "savings_rules", ["user_id"])


def downgrade() -> None:
    for table in ("savings_rules", "goal_contributions", "reservations", "savings_goals"):
        op.drop_table(table)
