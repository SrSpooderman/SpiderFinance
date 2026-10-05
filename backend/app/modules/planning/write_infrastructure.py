"""Generic persistence operations for planning aggregates on current tables."""

from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.infrastructure.models import (
    Debt, DebtPayment, IncomeReceipt, IncomeSource, RecurringExpense,
    RecurringPayment, ScheduledExpense, Transaction,
)
from app.modules.ledger.ports import LedgerRead
from app.infrastructure.snapshot import snapshot
from app.modules.planning.infrastructure import SqlPlanningReader

MODELS = {
    "income": IncomeSource, "recurring": RecurringExpense, "scheduled": ScheduledExpense,
    "debt": Debt, "receipt": IncomeReceipt, "recurring_payment": RecurringPayment,
    "debt_payment": DebtPayment, "transaction": Transaction,
}


class SqlPlanningStore:
    def __init__(self, session: Session, ledger: LedgerRead):
        self.session = session
        self.ledger = ledger

    def today(self, user_id: int) -> date:
        return self.ledger.today(user_id)

    def account(self, user_id: int, account_id: int) -> dict | None:
        return self.ledger.account(user_id, account_id)

    def category(self, user_id: int, category_id: int) -> dict | None:
        return self.ledger.category(user_id, category_id)

    def get(self, kind: str, user_id: int, item_id: int) -> dict | None:
        model = MODELS[kind]
        item = self.session.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
        return snapshot(item) if item else None

    def list(self, kind: str, user_id: int) -> list[dict]:
        model = MODELS[kind]
        order = model.due_date if kind == "scheduled" else model.id
        return [snapshot(item) for item in self.session.scalars(select(model).where(
            model.user_id == user_id
        ).order_by(order))]

    def create(self, kind: str, user_id: int, values: dict, commit: bool = True) -> dict:
        item = MODELS[kind](user_id=user_id, **values)
        self.session.add(item)
        self.session.flush()
        if commit:
            self.session.commit()
            self.session.refresh(item)
        return snapshot(item)

    def update(self, kind: str, user_id: int, item_id: int, changes: dict, commit: bool = True) -> dict:
        model = MODELS[kind]
        item = self.session.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
        for key, value in changes.items():
            setattr(item, key, value)
        self.session.flush()
        if commit:
            self.session.commit()
            self.session.refresh(item)
        return snapshot(item)

    def delete(self, kind: str, user_id: int, item_id: int) -> None:
        model = MODELS[kind]
        item = self.session.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
        self.session.delete(item)
        self.session.commit()

    def delete_related(self, kind: str, user_id: int, field: str, value: int) -> None:
        model = MODELS[kind]
        self.session.execute(delete(model).where(model.user_id == user_id, getattr(model, field) == value))

    def exists(self, kind: str, field: str, value, extra: dict | None = None) -> bool:
        model = MODELS[kind]
        clauses = [getattr(model, field) == value]
        for name, expected in (extra or {}).items():
            clauses.append(getattr(model, name) == expected)
        return self.session.scalar(select(model.id).where(*clauses).limit(1)) is not None

    def linked_any(self, transaction_id: int) -> bool:
        return any(self.exists(kind, "transaction_id", transaction_id)
                   for kind in ("receipt", "recurring_payment", "scheduled", "debt_payment"))

    def debt_remaining(self, user_id: int, debt_id: int, principal: Decimal) -> Decimal:
        return SqlPlanningReader(self.session).debt_remaining(user_id, debt_id, principal)

    def clear_other_primary(self, user_id: int, selected_id: int) -> None:
        for item in self.session.scalars(select(IncomeSource).where(
            IncomeSource.user_id == user_id, IncomeSource.id != selected_id, IncomeSource.is_primary == True
        )):
            item.is_primary = False

    def commit(self) -> None:
        self.session.commit()
