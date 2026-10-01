from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.infrastructure.models.common import TimestampMixin


class IncomeSource(TimestampMixin, Base):
    __tablename__ = "income_sources"
    __table_args__ = (Index("ix_income_sources_user", "user_id"), CheckConstraint("amount > 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    day_rule: Mapped[str] = mapped_column(String(32))
    day_of_month: Mapped[int | None] = mapped_column(Integer)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class RecurringExpense(TimestampMixin, Base):
    __tablename__ = "recurring_expenses"
    __table_args__ = (Index("ix_recurring_expenses_user", "user_id"), CheckConstraint("amount > 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    frequency: Mapped[str] = mapped_column(String(16))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ScheduledExpense(TimestampMixin, Base):
    __tablename__ = "scheduled_expenses"
    __table_args__ = (Index("ix_scheduled_expenses_user_due", "user_id", "due_date"), CheckConstraint("amount > 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="PLANNED")
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), unique=True)


class Debt(TimestampMixin, Base):
    __tablename__ = "debts"
    __table_args__ = (
        Index("ix_debts_user", "user_id"),
        CheckConstraint("principal > 0"),
        CheckConstraint("installment_amount > 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    principal: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    installment_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    starts_on: Mapped[date] = mapped_column(Date)
    due_day: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class IncomeReceipt(TimestampMixin, Base):
    __tablename__ = "income_receipts"
    __table_args__ = (UniqueConstraint("source_id", "due_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source_id: Mapped[int] = mapped_column(ForeignKey("income_sources.id", ondelete="RESTRICT"))
    due_date: Mapped[date] = mapped_column(Date)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), unique=True)


class RecurringPayment(TimestampMixin, Base):
    __tablename__ = "recurring_payments"
    __table_args__ = (UniqueConstraint("expense_id", "due_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expense_id: Mapped[int] = mapped_column(ForeignKey("recurring_expenses.id", ondelete="RESTRICT"))
    due_date: Mapped[date] = mapped_column(Date)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), unique=True)


class DebtPayment(TimestampMixin, Base):
    __tablename__ = "debt_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id", ondelete="RESTRICT"))
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), unique=True)
