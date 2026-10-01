from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import TransactionIn, TransactionOut, TransactionPage, TransactionPatch
from app.application.finance import account_balances, user_today, validate_transaction
from app.domain.types import TransactionType
from app.infrastructure.models import DebtPayment, IncomeReceipt, InvestmentContribution, InvestmentPosition, RecurringPayment, ScheduledExpense, Transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])


def get_transaction(db: DbSession, user_id: int, transaction_id: int) -> Transaction:
    movement = db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id))
    if movement is None:
        raise HTTPException(404, "Movimiento no encontrado")
    return movement


def ensure_not_linked(db: DbSession, transaction_id: int) -> None:
    for model in (DebtPayment, IncomeReceipt, InvestmentContribution, RecurringPayment, ScheduledExpense):
        if db.scalar(select(model.id).where(model.transaction_id == transaction_id).limit(1)):
            raise HTTPException(409, "El movimiento está vinculado a una obligación; desvincúlalo antes de modificarlo")


def ensure_investment_capacity(db: DbSession, user_id: int, old: Transaction | None, new: dict | None) -> None:
    today = user_today(db, user_id)

    def effects(values) -> dict[int, Decimal]:
        if values is None:
            return {}
        get = values.get if isinstance(values, dict) else lambda key: getattr(values, key)
        if get("status") != "CLEARED" or get("date") > today:
            return {}
        result: dict[int, Decimal] = {}
        source = get("source_account_id")
        destination = get("destination_account_id")
        if source is not None:
            result[source] = result.get(source, Decimal("0")) - get("amount")
        if destination is not None:
            result[destination] = result.get(destination, Decimal("0")) + get("amount")
        return result

    before = effects(old)
    after = effects(new)
    balances = account_balances(db, user_id)
    for account_id in before.keys() | after.keys():
        cost = Decimal(db.scalar(select(func.coalesce(func.sum(InvestmentPosition.cost_basis), 0)).where(
            InvestmentPosition.user_id == user_id, InvestmentPosition.account_id == account_id
        )) or 0)
        if cost and balances[account_id] + after.get(account_id, Decimal("0")) - before.get(account_id, Decimal("0")) < cost:
            raise HTTPException(409, "El movimiento dejaría una cuenta de inversión sin saldo para sus posiciones")


@router.get("", response_model=TransactionPage)
def list_transactions(
    user: CurrentUser, db: DbSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    date_from: date | None = None, date_to: date | None = None,
    account_id: int | None = None, type: TransactionType | None = None,
    category_id: int | None = None, search: str | None = None,
    min_amount: Decimal | None = Query(None, ge=0), max_amount: Decimal | None = Query(None, ge=0),
    is_fixed: bool | None = None, is_necessary: bool | None = None,
) -> TransactionPage:
    filters = [Transaction.user_id == user.id]
    if date_from:
        filters.append(Transaction.date >= date_from)
    if date_to:
        filters.append(Transaction.date <= date_to)
    if account_id is not None:
        filters.append(or_(Transaction.source_account_id == account_id, Transaction.destination_account_id == account_id))
    if type:
        filters.append(Transaction.type == type)
    if category_id is not None:
        filters.append(Transaction.category_id == category_id)
    if search:
        filters.append(Transaction.concept.ilike(f"%{search}%"))
    if min_amount is not None:
        filters.append(Transaction.amount >= min_amount)
    if max_amount is not None:
        filters.append(Transaction.amount <= max_amount)
    if is_fixed is not None:
        filters.append(Transaction.is_fixed == is_fixed)
    if is_necessary is not None:
        filters.append(Transaction.is_necessary == is_necessary)
    total = db.scalar(select(func.count(Transaction.id)).where(*filters)) or 0
    items = db.scalars(select(Transaction).where(*filters).order_by(Transaction.date.desc(), Transaction.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return TransactionPage(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionIn, user: CurrentUser, db: DbSession) -> Transaction:
    values = data.model_dump()
    validate_transaction(db, user.id, values)
    ensure_investment_capacity(db, user.id, None, values)
    movement = Transaction(user_id=user.id, **values)
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


@router.get("/{transaction_id}", response_model=TransactionOut)
def read_transaction(transaction_id: int, user: CurrentUser, db: DbSession) -> Transaction:
    return get_transaction(db, user.id, transaction_id)


@router.patch("/{transaction_id}", response_model=TransactionOut)
def update_transaction(transaction_id: int, data: TransactionPatch, user: CurrentUser, db: DbSession) -> Transaction:
    movement = get_transaction(db, user.id, transaction_id)
    ensure_not_linked(db, transaction_id)
    changes = data.model_dump(exclude_unset=True)
    if any(changes[key] is None for key in ("date", "type", "concept", "amount", "is_fixed", "is_necessary", "status") if key in changes):
        raise HTTPException(422, "Campo obligatorio nulo")
    values = {key: getattr(movement, key) for key in TransactionIn.model_fields}
    values.update(changes)
    validate_transaction(db, user.id, values)
    ensure_investment_capacity(db, user.id, movement, values)
    for key, value in changes.items():
        setattr(movement, key, value)
    db.commit()
    db.refresh(movement)
    return movement


@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, user: CurrentUser, db: DbSession) -> None:
    movement = get_transaction(db, user.id, transaction_id)
    ensure_not_linked(db, transaction_id)
    ensure_investment_capacity(db, user.id, movement, None)
    db.delete(movement)
    db.commit()
