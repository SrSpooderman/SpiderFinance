"""Read and write adapter for the existing budget table."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import Account, Budget, Category, Transaction
from app.modules.ledger.ports import LedgerRead
from app.infrastructure.snapshot import snapshot


class SqlBudgetStore:
    def __init__(self, session: Session, ledger: LedgerRead):
        self.session = session
        self.ledger = ledger

    def today(self, user_id: int) -> date:
        return self.ledger.today(user_id)

    def category(self, user_id: int, category_id: int) -> dict | None:
        return self.ledger.category(user_id, category_id)

    def categories(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Category).where(Category.user_id == user_id))]

    def accounts(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Account).where(Account.user_id == user_id))]

    def budgets(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Budget).where(
            Budget.user_id == user_id
        ).order_by(Budget.id))]

    def budget(self, user_id: int, budget_id: int) -> dict | None:
        item = self.session.scalar(select(Budget).where(Budget.id == budget_id, Budget.user_id == user_id))
        return snapshot(item) if item else None

    def add_budget(self, user_id: int, values: dict) -> dict:
        item = Budget(user_id=user_id, **values)
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return snapshot(item)

    def update_budget(self, user_id: int, budget_id: int, changes: dict) -> dict:
        item = self.session.scalar(select(Budget).where(Budget.id == budget_id, Budget.user_id == user_id))
        for key, value in changes.items():
            setattr(item, key, value)
        self.session.commit()
        self.session.refresh(item)
        return snapshot(item)

    def actuals(self, user_id: int, start: date, end: date) -> list[dict]:
        cutoff = min(end, self.today(user_id))
        return [snapshot(item) for item in self.session.scalars(select(Transaction).where(
            Transaction.user_id == user_id, Transaction.status == "CLEARED",
            Transaction.type.in_(["INCOME", "EXPENSE"]),
            Transaction.date >= start, Transaction.date <= cutoff,
        ))]
