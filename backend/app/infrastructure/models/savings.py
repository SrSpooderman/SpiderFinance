from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.infrastructure.models.common import TimestampMixin


class SavingsGoal(TimestampMixin, Base):
    __tablename__ = "savings_goals"
    __table_args__ = (Index("ix_savings_goals_user", "user_id"), CheckConstraint("target_amount > 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    target_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3))
    priority: Mapped[int] = mapped_column(default=1)
    due_date: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Reservation(TimestampMixin, Base):
    __tablename__ = "reservations"
    __table_args__ = (
        Index("ix_reservations_user", "user_id"),
        UniqueConstraint("user_id", "account_id", "goal_id", name="uq_reservation_account_goal"),
        CheckConstraint("amount >= 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("savings_goals.id", ondelete="RESTRICT"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))


class GoalContribution(TimestampMixin, Base):
    __tablename__ = "goal_contributions"
    __table_args__ = (Index("ix_goal_contributions_user_date", "user_id", "date"), CheckConstraint("amount <> 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[int] = mapped_column(ForeignKey("savings_goals.id", ondelete="RESTRICT"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    notes: Mapped[str | None] = mapped_column(Text)


class SavingsRule(TimestampMixin, Base):
    __tablename__ = "savings_rules"
    __table_args__ = (Index("ix_savings_rules_user", "user_id"), CheckConstraint("value > 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    income_source_id: Mapped[int] = mapped_column(ForeignKey("income_sources.id", ondelete="RESTRICT"))
    mode: Mapped[str] = mapped_column(String(16))
    value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
