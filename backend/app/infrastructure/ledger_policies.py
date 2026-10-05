"""SQL adapter for facts owned by other domains that guard ledger writes."""

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.infrastructure.models import (
    Budget, DebtPayment, ImportKey, IncomeReceipt, InvestmentContribution,
    InvestmentPosition, RecurringExpense, RecurringPayment, ScheduledExpense,
    Transaction,
)


class SqlLedgerPolicies:
    def __init__(self, session: Session):
        self.session = session

    def linked_transaction(self, transaction_id: int) -> bool:
        for model in (DebtPayment, ImportKey, IncomeReceipt, InvestmentContribution, RecurringPayment, ScheduledExpense):
            if self.session.scalar(select(model.id).where(model.transaction_id == transaction_id).limit(1)):
                return True
        return False

    def investment_cost(self, user_id: int, account_id: int) -> Decimal:
        return Decimal(self.session.scalar(select(func.coalesce(func.sum(InvestmentPosition.cost_basis), 0)).where(
            InvestmentPosition.user_id == user_id, InvestmentPosition.account_id == account_id
        )) or 0)

    def account_references(self, user_id: int, account_id: int) -> tuple[bool, bool, bool]:
        positions = bool(self.session.scalar(select(InvestmentPosition.id).where(
            InvestmentPosition.user_id == user_id, InvestmentPosition.account_id == account_id
        ).limit(1)))
        contributions = bool(self.session.scalar(select(InvestmentContribution.id).where(
            InvestmentContribution.user_id == user_id, InvestmentContribution.account_id == account_id
        ).limit(1)))
        movements = bool(self.session.scalar(select(Transaction.id).where(
            Transaction.user_id == user_id,
            or_(Transaction.source_account_id == account_id, Transaction.destination_account_id == account_id),
        ).limit(1)))
        return positions, contributions, movements

    def category_references(self, category_id: int) -> bool:
        return any(self.session.scalar(select(model.id).where(model.category_id == category_id).limit(1))
                   for model in (Transaction, RecurringExpense, ScheduledExpense, Budget))
