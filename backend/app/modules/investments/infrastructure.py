"""Portfolio adapter backed by the existing SQLAlchemy mappings."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.models import (
    Account, Debt, InvestmentContribution, InvestmentPosition, NetWorthSnapshot, Transaction,
)
from app.modules.ledger.ports import LedgerRead
from app.infrastructure.snapshot import snapshot
from app.modules.planning.ports import DebtReader


class SqlInvestmentStore:
    def __init__(self, session: Session, ledger: LedgerRead, planning: DebtReader):
        self.session = session
        self.ledger = ledger
        self.planning = planning

    def today(self, user_id: int) -> date:
        return self.ledger.today(user_id)

    def _one(self, model, user_id: int, item_id: int) -> dict | None:
        item = self.session.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
        return snapshot(item) if item else None

    def _all(self, query) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(query)]

    def _insert(self, model, values: dict) -> dict:
        item = model(**values)
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return snapshot(item)

    def account(self, user_id: int, account_id: int) -> dict | None:
        return self.ledger.account(user_id, account_id)

    def accounts(self, user_id: int) -> list[dict]:
        return self._all(select(Account).where(Account.user_id == user_id).order_by(Account.id))

    def balances(self, user_id: int) -> dict[int, Decimal]:
        return self.ledger.balances(user_id)

    def positions(self, user_id: int) -> list[dict]:
        return self._all(select(InvestmentPosition).where(InvestmentPosition.user_id == user_id)
                         .order_by(InvestmentPosition.account_id, InvestmentPosition.id))

    def position(self, user_id: int, position_id: int) -> dict | None:
        return self._one(InvestmentPosition, user_id, position_id)

    def allocated_cost(self, user_id: int, account_id: int, exclude_id: int | None) -> Decimal:
        query = select(func.coalesce(func.sum(InvestmentPosition.cost_basis), 0)).where(
            InvestmentPosition.user_id == user_id, InvestmentPosition.account_id == account_id
        )
        if exclude_id is not None:
            query = query.where(InvestmentPosition.id != exclude_id)
        return Decimal(self.session.scalar(query) or 0)

    def add_position(self, user_id: int, values: dict) -> dict:
        return self._insert(InvestmentPosition, {"user_id": user_id, **values})

    def update_position(self, user_id: int, position_id: int, changes: dict) -> dict:
        item = self.session.scalar(select(InvestmentPosition).where(
            InvestmentPosition.id == position_id, InvestmentPosition.user_id == user_id
        ))
        for key, value in changes.items():
            setattr(item, key, value)
        self.session.commit()
        self.session.refresh(item)
        return snapshot(item)

    def delete_position(self, user_id: int, position_id: int) -> None:
        item = self.session.scalar(select(InvestmentPosition).where(
            InvestmentPosition.id == position_id, InvestmentPosition.user_id == user_id
        ))
        self.session.delete(item)
        self.session.commit()

    def transaction(self, user_id: int, transaction_id: int) -> dict | None:
        return self._one(Transaction, user_id, transaction_id)

    def contribution_for_transaction(self, transaction_id: int) -> bool:
        return bool(self.session.scalar(select(InvestmentContribution.id).where(
            InvestmentContribution.transaction_id == transaction_id
        ).limit(1)))

    def contributions(self, user_id: int) -> list[dict]:
        return self._all(select(InvestmentContribution).where(InvestmentContribution.user_id == user_id)
                         .order_by(InvestmentContribution.id.desc()))

    def contribution(self, user_id: int, contribution_id: int) -> dict | None:
        return self._one(InvestmentContribution, user_id, contribution_id)

    def add_contribution(self, user_id: int, account_id: int, transaction_id: int) -> dict:
        return self._insert(InvestmentContribution, {"user_id": user_id, "account_id": account_id,
                                                      "transaction_id": transaction_id})

    def delete_contribution(self, user_id: int, contribution_id: int) -> None:
        item = self.session.scalar(select(InvestmentContribution).where(
            InvestmentContribution.id == contribution_id, InvestmentContribution.user_id == user_id
        ))
        self.session.delete(item)
        self.session.commit()

    def debts(self, user_id: int) -> list[dict]:
        result = []
        for item in self.session.scalars(select(Debt).where(Debt.user_id == user_id)):
            debt = snapshot(item)
            debt["remaining"] = self.planning.debt_remaining(user_id, item.id, item.principal)
            result.append(debt)
        return result

    def snapshots(self, user_id: int) -> list[dict]:
        return self._all(select(NetWorthSnapshot).where(NetWorthSnapshot.user_id == user_id)
                         .order_by(NetWorthSnapshot.date.desc(), NetWorthSnapshot.currency))

    def snapshot_exists(self, user_id: int, day: date) -> bool:
        return bool(self.session.scalar(select(NetWorthSnapshot.id).where(
            NetWorthSnapshot.user_id == user_id, NetWorthSnapshot.date == day
        ).limit(1)))

    def add_snapshots(self, user_id: int, day: date, currencies: list[dict]) -> list[dict]:
        items = [NetWorthSnapshot(user_id=user_id, date=day, currency=item["currency"],
                                  assets=item["assets"], liabilities=item["liabilities"],
                                  net_worth=item["net_worth"]) for item in currencies]
        self.session.add_all(items)
        self.session.commit()
        for item in items:
            self.session.refresh(item)
        return [snapshot(item) for item in items]
