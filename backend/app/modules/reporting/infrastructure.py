from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import Account, Category, Reservation, Transaction
from app.modules.ledger.ports import LedgerRead
from app.infrastructure.snapshot import snapshot


class SqlDashboardReader:
    def __init__(self, session: Session, ledger: LedgerRead):
        self.session = session
        self.ledger = ledger

    def today(self, user_id: int) -> date:
        return self.ledger.today(user_id)

    def accounts(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Account).where(Account.user_id == user_id))]

    def balances(self, user_id: int, day: date) -> dict[int, Decimal]:
        return self.ledger.balances(user_id, day)

    def reservations(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Reservation).where(
            Reservation.user_id == user_id, Reservation.amount > 0
        ))]

    def categories(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Category).where(Category.user_id == user_id))]

    def expenses(self, user_id: int, start: date, end: date) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Transaction).where(
            Transaction.user_id == user_id, Transaction.type == "EXPENSE", Transaction.status == "CLEARED",
            Transaction.date >= start, Transaction.date <= end,
        ))]

    def recent(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Transaction).where(
            Transaction.user_id == user_id
        ).order_by(Transaction.date.desc(), Transaction.id.desc()).limit(5))]
