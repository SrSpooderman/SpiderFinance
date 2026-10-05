"""Existing tables exposed as forecasting read models."""

from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.infrastructure.models import Account, Reservation, Transaction
from app.modules.ledger.ports import LedgerRead
from app.infrastructure.snapshot import snapshot


class SqlForecastReader:
    def __init__(self, session: Session, ledger: LedgerRead):
        self.session = session
        self.ledger = ledger

    def active_accounts(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Account).where(
            Account.user_id == user_id, Account.active == True
        ).order_by(Account.id))]

    def balances(self, user_id: int, as_of: date) -> dict[int, Decimal]:
        return self.ledger.balances(user_id, as_of)

    def reservations(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Reservation).where(
            Reservation.user_id == user_id, Reservation.amount > 0
        ))]

    def pending_movements(self, user_id: int, start: date, end: date) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Transaction).where(
            Transaction.user_id == user_id, Transaction.date <= end,
            or_(Transaction.status == "PENDING", Transaction.date > start),
        ).order_by(Transaction.date, Transaction.id))]
