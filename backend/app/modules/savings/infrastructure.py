"""SQLAlchemy adapter for savings; the database mappings remain unchanged."""

from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.infrastructure.models import Account, GoalContribution, IncomeSource, Reservation, SavingsGoal, SavingsRule
from app.modules.ledger.ports import LedgerRead
from app.infrastructure.snapshot import snapshot


class SqlSavingsStore:
    def __init__(self, session: Session, ledger: LedgerRead):
        self.session = session
        self.ledger = ledger

    def today(self, user_id: int) -> date:
        return self.ledger.today(user_id)

    def _one(self, model, user_id: int, item_id: int, lock: bool = False) -> dict | None:
        query = select(model).where(model.id == item_id, model.user_id == user_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        item = self.session.scalar(query)
        return snapshot(item) if item else None

    def _all(self, query) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(query)]

    def _insert(self, model, values: dict) -> dict:
        item = model(**values)
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return snapshot(item)

    def _update(self, model, user_id: int, item_id: int, changes: dict) -> dict:
        item = self.session.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
        for key, value in changes.items():
            setattr(item, key, value)
        self.session.commit()
        self.session.refresh(item)
        return snapshot(item)

    def account(self, user_id: int, account_id: int, lock: bool = False) -> dict | None:
        return self._one(Account, user_id, account_id, lock)

    def accounts(self, user_id: int) -> list[dict]:
        return self._all(select(Account).where(Account.user_id == user_id))

    def account_balance(self, user_id: int, account_id: int) -> Decimal:
        return self.ledger.balance(user_id, account_id)

    def goals(self, user_id: int) -> list[dict]:
        return self._all(select(SavingsGoal).where(SavingsGoal.user_id == user_id).order_by(SavingsGoal.priority, SavingsGoal.id))

    def goal(self, user_id: int, goal_id: int) -> dict | None:
        return self._one(SavingsGoal, user_id, goal_id)

    def funded(self, goal_id: int) -> Decimal:
        return Decimal(self.session.scalar(select(func.coalesce(func.sum(Reservation.amount), 0)).where(
            Reservation.goal_id == goal_id
        )) or 0)

    def add_goal(self, user_id: int, values: dict) -> dict:
        return self._insert(SavingsGoal, {"user_id": user_id, **values})

    def update_goal(self, user_id: int, goal_id: int, changes: dict) -> dict:
        return self._update(SavingsGoal, user_id, goal_id, changes)

    def reservations(self, user_id: int) -> list[dict]:
        return self._all(select(Reservation).where(Reservation.user_id == user_id, Reservation.amount > 0).order_by(Reservation.id))

    def reservation(self, user_id: int, reservation_id: int, lock: bool = False) -> dict | None:
        return self._one(Reservation, user_id, reservation_id, lock)

    def reserved_on_account(self, account_id: int) -> Decimal:
        return Decimal(self.session.scalar(select(func.coalesce(func.sum(Reservation.amount), 0)).where(
            Reservation.account_id == account_id
        )) or 0)

    def reservation_for(self, user_id: int, account_id: int, goal_id: int | None) -> dict | None:
        item = self.session.scalar(select(Reservation).where(
            Reservation.user_id == user_id, Reservation.account_id == account_id, Reservation.goal_id == goal_id
        ))
        return snapshot(item) if item else None

    def set_reservation(self, user_id: int, account_id: int, goal_id: int | None, amount: Decimal) -> dict:
        item = self.session.scalar(select(Reservation).where(
            Reservation.user_id == user_id, Reservation.account_id == account_id, Reservation.goal_id == goal_id
        ))
        if item is None:
            item = Reservation(user_id=user_id, account_id=account_id, goal_id=goal_id, amount=Decimal("0"))
            self.session.add(item)
            self.session.flush()
        item.amount = amount
        self.session.flush()
        return snapshot(item)

    def add_contribution(self, user_id: int, goal_id: int, account_id: int, day: date, amount: Decimal, notes: str | None) -> None:
        self.session.add(GoalContribution(user_id=user_id, goal_id=goal_id, account_id=account_id,
                                          date=day, amount=amount, notes=notes))

    def contributions(self, user_id: int) -> list[dict]:
        return self._all(select(GoalContribution).where(GoalContribution.user_id == user_id)
                         .order_by(GoalContribution.date.desc(), GoalContribution.id.desc()))

    def rules(self, user_id: int) -> list[dict]:
        return self._all(select(SavingsRule).where(SavingsRule.user_id == user_id).order_by(SavingsRule.id))

    def rule(self, user_id: int, rule_id: int) -> dict | None:
        return self._one(SavingsRule, user_id, rule_id)

    def source(self, user_id: int, source_id: int) -> dict | None:
        return self._one(IncomeSource, user_id, source_id)

    def sources(self, user_id: int) -> list[dict]:
        return self._all(select(IncomeSource).where(IncomeSource.user_id == user_id, IncomeSource.active == True))

    def add_rule(self, user_id: int, values: dict) -> dict:
        return self._insert(SavingsRule, {"user_id": user_id, **values})

    def update_rule(self, user_id: int, rule_id: int, changes: dict) -> dict:
        return self._update(SavingsRule, user_id, rule_id, changes)

    def delete_rules_for_source(self, user_id: int, source_id: int) -> None:
        self.session.execute(delete(SavingsRule).where(
            SavingsRule.user_id == user_id, SavingsRule.income_source_id == source_id
        ))

    def commit(self) -> None:
        self.session.commit()
