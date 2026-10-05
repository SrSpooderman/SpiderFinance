"""Compatibility functions for the CLI and older imports."""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import Account, Category
from app.infrastructure.ledger_policies import SqlLedgerPolicies
from app.modules.errors import UseCaseError
from app.modules.ledger.application import Ledger
from app.modules.ledger.infrastructure import SqlLedgerStore


def get_account(db: Session, user_id: int, account_id: int) -> Account:
    item = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user_id))
    if item is None:
        raise HTTPException(404, "Cuenta no encontrada")
    return item


def get_category(db: Session, user_id: int, category_id: int) -> Category:
    item = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user_id))
    if item is None:
        raise HTTPException(404, "Categoría no encontrada")
    return item


def user_today(db: Session, user_id: int) -> date:
    return SqlLedgerStore(db).today(user_id)


def validate_transaction(db: Session, user_id: int, data: dict) -> None:
    try:
        Ledger(SqlLedgerStore(db), SqlLedgerPolicies(db)).validate_transaction(user_id, data)
    except UseCaseError as exc:
        raise HTTPException(exc.status, exc.message) from exc


def account_balances(db: Session, user_id: int, as_of: date | None = None) -> dict[int, Decimal]:
    return Ledger(SqlLedgerStore(db), SqlLedgerPolicies(db)).balances(user_id, as_of)


def account_balance(db: Session, user_id: int, account_id: int, as_of: date | None = None) -> Decimal:
    return Ledger(SqlLedgerStore(db), SqlLedgerPolicies(db)).balance(user_id, account_id, as_of)
