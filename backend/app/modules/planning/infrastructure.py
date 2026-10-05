"""Planning read adapter using the unchanged SQLAlchemy models."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.models import (
    Account, Debt, DebtPayment, IncomeReceipt, IncomeSource,
    RecurringExpense, RecurringPayment, ScheduledExpense, Transaction,
)
from app.infrastructure.snapshot import snapshot


class SqlPlanningReader:
    def __init__(self, session: Session):
        self.session = session

    def accounts(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Account).where(Account.user_id == user_id))]

    def income_sources(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(IncomeSource).where(
            IncomeSource.user_id == user_id, IncomeSource.active == True
        ).order_by(IncomeSource.id))]

    def income_receipt_dates(self, source_id: int) -> set[date]:
        return set(self.session.scalars(select(IncomeReceipt.due_date).where(IncomeReceipt.source_id == source_id)))

    def recurring_expenses(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(RecurringExpense).where(
            RecurringExpense.user_id == user_id, RecurringExpense.active == True
        ))]

    def recurring_payment_dates(self, expense_id: int) -> set[date]:
        return set(self.session.scalars(select(RecurringPayment.due_date).where(RecurringPayment.expense_id == expense_id)))

    def scheduled_expenses(self, user_id: int, end: date) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(ScheduledExpense).where(
            ScheduledExpense.user_id == user_id, ScheduledExpense.status == "PLANNED", ScheduledExpense.due_date <= end
        ))]

    def debts(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Debt).where(
            Debt.user_id == user_id, Debt.active == True
        ))]

    def debt_remaining(self, user_id: int, debt_id: int, principal: Decimal) -> Decimal:
        paid = self.session.scalar(select(func.coalesce(func.sum(Transaction.amount), 0))
            .join(DebtPayment, DebtPayment.transaction_id == Transaction.id)
            .where(DebtPayment.debt_id == debt_id, DebtPayment.user_id == user_id)) or Decimal("0")
        return principal - Decimal(paid)
