from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.types import TransactionType
from app.infrastructure.models import Account, Category, Transaction, UserSettings


def get_account(db: Session, user_id: int, account_id: int) -> Account:
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user_id))
    if account is None:
        raise HTTPException(404, "Cuenta no encontrada")
    return account


def get_category(db: Session, user_id: int, category_id: int) -> Category:
    category = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user_id))
    if category is None:
        raise HTTPException(404, "Categoría no encontrada")
    return category


def user_today(db: Session, user_id: int) -> date:
    preferences = db.get(UserSettings, user_id)
    return datetime.now(ZoneInfo(preferences.timezone)).date()


def validate_transaction(db: Session, user_id: int, data: dict) -> None:
    kind = data["type"]
    source_id = data.get("source_account_id")
    destination_id = data.get("destination_account_id")
    category_id = data.get("category_id")
    if kind == TransactionType.INCOME and (source_id is not None or destination_id is None):
        raise HTTPException(422, "Un ingreso requiere solo una cuenta destino")
    if kind == TransactionType.EXPENSE and (source_id is None or destination_id is not None):
        raise HTTPException(422, "Un gasto requiere solo una cuenta origen")
    if kind == TransactionType.TRANSFER and (source_id is None or destination_id is None or source_id == destination_id):
        raise HTTPException(422, "Una transferencia requiere dos cuentas distintas")
    if kind == TransactionType.ADJUSTMENT and ((source_id is None) == (destination_id is None)):
        raise HTTPException(422, "Un ajuste requiere exactamente una cuenta")
    source = get_account(db, user_id, source_id) if source_id is not None else None
    destination = get_account(db, user_id, destination_id) if destination_id is not None else None
    if source and destination and source.currency != destination.currency:
        raise HTTPException(422, "La transferencia entre monedas distintas requiere conversión")
    if category_id is not None:
        get_category(db, user_id, category_id)


def account_balances(db: Session, user_id: int, as_of: date | None = None) -> dict[int, Decimal]:
    as_of = as_of or user_today(db, user_id)
    accounts = db.scalars(select(Account).where(Account.user_id == user_id)).all()
    balances = {account.id: account.initial_balance for account in accounts}
    movements = db.scalars(
        select(Transaction).where(Transaction.user_id == user_id, Transaction.status == "CLEARED", Transaction.date <= as_of)
    )
    for movement in movements:
        if movement.source_account_id is not None:
            balances[movement.source_account_id] -= movement.amount
        if movement.destination_account_id is not None:
            balances[movement.destination_account_id] += movement.amount
    return balances


def account_balance(db: Session, user_id: int, account_id: int, as_of: date | None = None) -> Decimal:
    get_account(db, user_id, account_id)
    return account_balances(db, user_id, as_of)[account_id]
