from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession
from app.api.investment_schemas import (
    ContributionIn, ContributionOut, NetWorthAccount, NetWorthCurrency, NetWorthOut,
    PositionIn, PositionOut, PositionPatch, SnapshotOut,
)
from app.api.planning import debt_remaining
from app.application.finance import account_balances, get_account, user_today
from app.infrastructure.models import (
    Account, Debt, InvestmentContribution, InvestmentPosition, NetWorthSnapshot, Transaction,
)

router = APIRouter(tags=["investments"])


def owned_position(db: DbSession, user_id: int, item_id: int) -> InvestmentPosition:
    item = db.scalar(select(InvestmentPosition).where(
        InvestmentPosition.id == item_id, InvestmentPosition.user_id == user_id
    ))
    if item is None:
        raise HTTPException(404, "Posición no encontrada")
    return item


def investment_account(db: DbSession, user_id: int, account_id: int) -> Account:
    account = get_account(db, user_id, account_id)
    if account.type != "INVESTMENT":
        raise HTTPException(422, "La cuenta debe ser de tipo inversión")
    return account


def validate_position(db: DbSession, user_id: int, values: PositionIn, exclude_id: int | None = None):
    investment_account(db, user_id, values.account_id)
    if values.valued_on > user_today(db, user_id):
        raise HTTPException(422, "La valoración no puede estar en el futuro")
    allocated = Decimal(db.scalar(select(func.coalesce(func.sum(InvestmentPosition.cost_basis), 0)).where(
        InvestmentPosition.user_id == user_id, InvestmentPosition.account_id == values.account_id,
        InvestmentPosition.id != exclude_id if exclude_id is not None else True,
    )) or 0)
    if allocated + values.cost_basis > account_balances(db, user_id)[values.account_id]:
        raise HTTPException(422, "El coste de las posiciones supera el saldo aportado a la cuenta")


@router.get("/investments/positions", response_model=list[PositionOut])
def list_positions(user: CurrentUser, db: DbSession):
    return db.scalars(select(InvestmentPosition).where(
        InvestmentPosition.user_id == user.id
    ).order_by(InvestmentPosition.account_id, InvestmentPosition.id)).all()


@router.post("/investments/positions", response_model=PositionOut, status_code=201)
def create_position(data: PositionIn, user: CurrentUser, db: DbSession):
    validate_position(db, user.id, data)
    item = InvestmentPosition(user_id=user.id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/investments/positions/{item_id}", response_model=PositionOut)
def patch_position(item_id: int, data: PositionPatch, user: CurrentUser, db: DbSession):
    item = owned_position(db, user.id, item_id)
    changes = data.model_dump(exclude_unset=True)
    values = {key: getattr(item, key) for key in PositionIn.model_fields}
    values.update(changes)
    try:
        validated = PositionIn.model_validate(values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    validate_position(db, user.id, validated, item.id)
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/investments/positions/{item_id}", status_code=204)
def delete_position(item_id: int, user: CurrentUser, db: DbSession):
    item = owned_position(db, user.id, item_id)
    db.delete(item)
    db.commit()


@router.get("/investments/contributions", response_model=list[ContributionOut])
def list_contributions(user: CurrentUser, db: DbSession):
    return db.scalars(select(InvestmentContribution).where(
        InvestmentContribution.user_id == user.id
    ).order_by(InvestmentContribution.id.desc())).all()


@router.post("/investments/contributions", response_model=ContributionOut, status_code=201)
def link_contribution(data: ContributionIn, user: CurrentUser, db: DbSession):
    movement = db.scalar(select(Transaction).where(
        Transaction.id == data.transaction_id, Transaction.user_id == user.id
    ))
    if movement is None:
        raise HTTPException(404, "Movimiento no encontrado")
    if movement.type != "TRANSFER" or movement.status != "CLEARED" or movement.date > user_today(db, user.id):
        raise HTTPException(422, "La aportación debe ser una transferencia confirmada y no futura")
    investment_account(db, user.id, movement.destination_account_id)
    if db.scalar(select(InvestmentContribution.id).where(InvestmentContribution.transaction_id == movement.id)):
        raise HTTPException(409, "La transferencia ya está vinculada")
    item = InvestmentContribution(
        user_id=user.id, account_id=movement.destination_account_id, transaction_id=movement.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/investments/contributions/{item_id}", status_code=204)
def unlink_contribution(item_id: int, user: CurrentUser, db: DbSession):
    item = db.scalar(select(InvestmentContribution).where(
        InvestmentContribution.id == item_id, InvestmentContribution.user_id == user.id
    ))
    if item is None:
        raise HTTPException(404, "Aportación no encontrada")
    db.delete(item)
    db.commit()


def net_worth(db: DbSession, user_id: int) -> NetWorthOut:
    today = user_today(db, user_id)
    balances = account_balances(db, user_id)
    positions = list(db.scalars(select(InvestmentPosition).where(InvestmentPosition.user_id == user_id)))
    by_account: dict[int, list[InvestmentPosition]] = {}
    for position in positions:
        by_account.setdefault(position.account_id, []).append(position)
    totals: dict[str, dict[str, Decimal]] = {}
    accounts_out = []
    for account in db.scalars(select(Account).where(Account.user_id == user_id).order_by(Account.id)):
        balance = balances[account.id]
        holdings = by_account.get(account.id, [])
        cost = sum((item.cost_basis for item in holdings), Decimal("0"))
        position_value = sum((item.market_value for item in holdings), Decimal("0"))
        uninvested = balance - cost if account.type == "INVESTMENT" else balance
        value = uninvested + position_value if account.type == "INVESTMENT" else balance
        accounts_out.append(NetWorthAccount(
            id=account.id, name=account.name, type=account.type, currency=account.currency,
            book_balance=balance, position_value=position_value,
            uninvested_cash=uninvested, asset_value=value,
        ))
        currency = totals.setdefault(account.currency, {"assets": Decimal("0"), "liabilities": Decimal("0")})
        if value >= 0:
            currency["assets"] += value
        else:
            currency["liabilities"] -= value
    for debt in db.scalars(select(Debt).where(Debt.user_id == user_id)):
        account = get_account(db, user_id, debt.account_id)
        currency = totals.setdefault(account.currency, {"assets": Decimal("0"), "liabilities": Decimal("0")})
        currency["liabilities"] += debt_remaining(db, debt)
    return NetWorthOut(
        date=today,
        currencies=[NetWorthCurrency(
            currency=currency, assets=values["assets"], liabilities=values["liabilities"],
            net_worth=values["assets"] - values["liabilities"],
        ) for currency, values in sorted(totals.items())],
        accounts=accounts_out,
    )


@router.get("/net-worth", response_model=NetWorthOut)
def read_net_worth(user: CurrentUser, db: DbSession):
    return net_worth(db, user.id)


@router.get("/net-worth/snapshots", response_model=list[SnapshotOut])
def list_snapshots(user: CurrentUser, db: DbSession):
    return db.scalars(select(NetWorthSnapshot).where(
        NetWorthSnapshot.user_id == user.id
    ).order_by(NetWorthSnapshot.date.desc(), NetWorthSnapshot.currency)).all()


@router.post("/net-worth/snapshots", response_model=list[SnapshotOut], status_code=201)
def create_snapshot(user: CurrentUser, db: DbSession):
    report = net_worth(db, user.id)
    if db.scalar(select(NetWorthSnapshot.id).where(
        NetWorthSnapshot.user_id == user.id, NetWorthSnapshot.date == report.date
    ).limit(1)):
        raise HTTPException(409, "Ya existe un snapshot para hoy")
    items = [NetWorthSnapshot(
        user_id=user.id, date=report.date, currency=item.currency,
        assets=item.assets, liabilities=item.liabilities, net_worth=item.net_worth,
    ) for item in report.currencies]
    db.add_all(items)
    db.commit()
    for item in items:
        db.refresh(item)
    return items
