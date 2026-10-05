"""SQLAlchemy adapter for the existing database schema."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.infrastructure.snapshot import snapshot
from app.infrastructure.models import Account, Category, Transaction, UserSettings
from app.modules.ledger.domain import balances as calculate_balances


class SqlLedgerStore:
    def __init__(self, session: Session):
        self.session = session

    def today(self, user_id: int) -> date:
        preferences = self.session.get(UserSettings, user_id)
        return datetime.now(ZoneInfo(preferences.timezone)).date()

    def account(self, user_id: int, account_id: int) -> dict | None:
        item = self.session.scalar(select(Account).where(Account.id == account_id, Account.user_id == user_id))
        return snapshot(item) if item else None

    def accounts(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(
            select(Account).where(Account.user_id == user_id).order_by(Account.id)
        )]

    def category(self, user_id: int, category_id: int) -> dict | None:
        item = self.session.scalar(select(Category).where(Category.id == category_id, Category.user_id == user_id))
        return snapshot(item) if item else None

    def categories(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(
            select(Category).where(Category.user_id == user_id).order_by(Category.parent_id, Category.name)
        )]

    def cleared_movements(self, user_id: int, as_of: date) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Transaction).where(
            Transaction.user_id == user_id, Transaction.status == "CLEARED", Transaction.date <= as_of
        ))]

    def balances(self, user_id: int, as_of: date | None = None) -> dict[int, Decimal]:
        return calculate_balances(self.accounts(user_id), self.cleared_movements(
            user_id, as_of or self.today(user_id)
        ))

    def balance(self, user_id: int, account_id: int, as_of: date | None = None) -> Decimal:
        return self.balances(user_id, as_of)[account_id]

    def transaction(self, user_id: int, transaction_id: int) -> dict | None:
        item = self.session.scalar(select(Transaction).where(
            Transaction.id == transaction_id, Transaction.user_id == user_id
        ))
        return snapshot(item) if item else None

    def transactions(self, user_id: int, filters: dict, page: int, page_size: int) -> tuple[list[dict], int]:
        clauses = [Transaction.user_id == user_id]
        for key in ("date_from", "date_to", "account_id", "type", "category_id", "search",
                    "min_amount", "max_amount", "is_fixed", "is_necessary"):
            value = filters.get(key)
            if value is None or value == "":
                continue
            if key == "date_from":
                clauses.append(Transaction.date >= value)
            elif key == "date_to":
                clauses.append(Transaction.date <= value)
            elif key == "account_id":
                clauses.append(or_(Transaction.source_account_id == value, Transaction.destination_account_id == value))
            elif key == "search":
                clauses.append(Transaction.concept.ilike(f"%{value}%"))
            elif key == "min_amount":
                clauses.append(Transaction.amount >= value)
            elif key == "max_amount":
                clauses.append(Transaction.amount <= value)
            else:
                clauses.append(getattr(Transaction, key) == value)
        count = self.session.scalar(select(func.count(Transaction.id)).where(*clauses)) or 0
        items = self.session.scalars(select(Transaction).where(*clauses).order_by(
            Transaction.date.desc(), Transaction.id.desc()
        ).offset((page - 1) * page_size).limit(page_size)).all()
        return [snapshot(item) for item in items], count

    def sibling_category(self, user_id: int, name: str, parent_id: int | None, exclude_id: int | None) -> bool:
        query = select(Category.id).where(Category.user_id == user_id, Category.parent_id == parent_id, Category.name == name)
        if exclude_id is not None:
            query = query.where(Category.id != exclude_id)
        return self.session.scalar(query.limit(1)) is not None

    def has_child_categories(self, category_id: int) -> bool:
        return self.session.scalar(select(Category.id).where(Category.parent_id == category_id).limit(1)) is not None

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

    def add_account(self, user_id: int, values: dict) -> dict:
        return self._insert(Account, {"user_id": user_id, **values})

    def update_account(self, user_id: int, account_id: int, changes: dict) -> dict:
        return self._update(Account, user_id, account_id, changes)

    def add_category(self, user_id: int, values: dict) -> dict:
        return self._insert(Category, {"user_id": user_id, **values})

    def update_category(self, user_id: int, category_id: int, changes: dict) -> dict:
        return self._update(Category, user_id, category_id, changes)

    def delete_category(self, user_id: int, category_id: int) -> None:
        item = self.session.scalar(select(Category).where(Category.id == category_id, Category.user_id == user_id))
        self.session.delete(item)
        self.session.commit()

    def add_transaction(self, user_id: int, values: dict) -> dict:
        return self._insert(Transaction, {**values, "user_id": user_id})

    def update_transaction(self, user_id: int, transaction_id: int, changes: dict) -> dict:
        return self._update(Transaction, user_id, transaction_id, changes)

    def delete_transaction(self, user_id: int, transaction_id: int) -> None:
        item = self.session.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id))
        self.session.delete(item)
        self.session.commit()
