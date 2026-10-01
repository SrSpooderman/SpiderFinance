from decimal import Decimal

from fastapi import APIRouter, HTTPException
from sqlalchemy import or_, select

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import AccountIn, AccountOut, AccountPatch, ReconcileIn, ReconcileOut
from app.application.finance import account_balance, account_balances, get_account
from app.domain.types import TransactionType
from app.infrastructure.models import Account, InvestmentContribution, InvestmentPosition, Transaction

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(user: CurrentUser, db: DbSession) -> list[AccountOut]:
    accounts = db.scalars(select(Account).where(Account.user_id == user.id).order_by(Account.id)).all()
    balances = account_balances(db, user.id)
    return [AccountOut.model_validate(account).model_copy(update={"balance": balances[account.id]}) for account in accounts]


@router.post("", response_model=AccountOut, status_code=201)
def create_account(data: AccountIn, user: CurrentUser, db: DbSession) -> AccountOut:
    account = Account(user_id=user.id, **data.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return AccountOut.model_validate(account).model_copy(update={"balance": account.initial_balance})


@router.get("/{account_id}", response_model=AccountOut)
def read_account(account_id: int, user: CurrentUser, db: DbSession) -> AccountOut:
    account = get_account(db, user.id, account_id)
    return AccountOut.model_validate(account).model_copy(update={"balance": account_balance(db, user.id, account_id)})


@router.get("/{account_id}/balance", response_model=dict[str, Decimal])
def read_balance(account_id: int, user: CurrentUser, db: DbSession) -> dict[str, Decimal]:
    return {"balance": account_balance(db, user.id, account_id)}


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, data: AccountPatch, user: CurrentUser, db: DbSession) -> AccountOut:
    account = get_account(db, user.id, account_id)
    changes = data.model_dump(exclude_unset=True)
    if any(changes.get(key) is None for key in ("name", "type", "initial_balance", "currency", "active") if key in changes):
        raise HTTPException(422, "Campo obligatorio nulo")
    has_positions = db.scalar(select(InvestmentPosition.id).where(
        InvestmentPosition.user_id == user.id, InvestmentPosition.account_id == account_id
    ).limit(1))
    if has_positions and (
        ("type" in changes and changes["type"] != account.type)
        or ("currency" in changes and changes["currency"] != account.currency)
        or ("initial_balance" in changes and changes["initial_balance"] != account.initial_balance)
    ):
        raise HTTPException(409, "La cuenta tiene posiciones de inversión; corrígelas antes de cambiar tipo, moneda o saldo inicial")
    has_contributions = db.scalar(select(InvestmentContribution.id).where(
        InvestmentContribution.user_id == user.id, InvestmentContribution.account_id == account_id
    ).limit(1))
    if has_contributions and "type" in changes and changes["type"] != account.type:
        raise HTTPException(409, "La cuenta tiene aportaciones de inversión vinculadas")
    if "initial_balance" in changes or "currency" in changes:
        has_movements = db.scalar(select(Transaction.id).where(
            Transaction.user_id == user.id,
            or_(Transaction.source_account_id == account_id, Transaction.destination_account_id == account_id),
        ).limit(1))
        if has_movements:
            raise HTTPException(409, "Con movimientos existentes, usa conciliación y no cambies el saldo inicial ni la moneda")
    for key, value in changes.items():
        setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return AccountOut.model_validate(account).model_copy(update={"balance": account_balance(db, user.id, account_id)})


@router.post("/{account_id}/reconcile", response_model=ReconcileOut)
def reconcile(account_id: int, data: ReconcileIn, user: CurrentUser, db: DbSession) -> ReconcileOut:
    account = get_account(db, user.id, account_id)
    difference = data.observed_balance - account_balance(db, user.id, account_id, data.date)
    if difference == 0:
        return ReconcileOut(difference=Decimal("0.00"), transaction=None)
    movement = Transaction(
        user_id=user.id, date=data.date, type=TransactionType.ADJUSTMENT,
        source_account_id=account.id if difference < 0 else None,
        destination_account_id=account.id if difference > 0 else None,
        concept="Ajuste de conciliación", amount=abs(difference),
        notes=data.notes, status="CLEARED", reconciliation=True,
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return ReconcileOut(difference=difference, transaction=movement)
