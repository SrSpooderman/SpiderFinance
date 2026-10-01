from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.api.forecast import salary_cycle
from app.api.schemas import ORMModel
from app.application.finance import get_category, user_today
from app.infrastructure.models import Account, Budget, Category, Transaction

router = APIRouter(tags=["budgets"])
Period = Literal["MONTH", "SALARY_CYCLE"]


class BudgetIn(BaseModel):
    category_id: int | None = None
    period: Period
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    active: bool = True


class BudgetPatch(BaseModel):
    category_id: int | None = None
    period: Period | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    active: bool | None = None


class BudgetOut(ORMModel, BudgetIn):
    id: int


class BudgetStatus(BudgetOut):
    start: date | None
    end: date | None
    spent: Decimal | None
    remaining: Decimal | None


class CategorySpend(BaseModel):
    category_id: int | None
    name: str
    currency: str
    amount: Decimal


class DailySpend(BaseModel):
    date: date
    currency: str
    amount: Decimal


class Statistics(BaseModel):
    period: Period
    start: date
    end: date
    income_by_currency: dict[str, Decimal]
    expense_by_currency: dict[str, Decimal]
    expenses_by_category: list[CategorySpend]
    daily_expenses: list[DailySpend]


def window(db: DbSession, user_id: int, period: Period, as_of: date) -> tuple[date, date] | None:
    if period == "MONTH":
        return as_of.replace(day=1), as_of.replace(day=monthrange(as_of.year, as_of.month)[1])
    cycle = salary_cycle(db, user_id, as_of)
    if cycle.current_start is None or cycle.current_end is None:
        return None
    return cycle.current_start, cycle.current_end


def checked_category(db: DbSession, user_id: int, category_id: int | None):
    if category_id is not None:
        get_category(db, user_id, category_id)


def ensure_unique(db: DbSession, user_id: int, data: BudgetIn, exclude_id: int | None = None):
    query = select(Budget).where(
        Budget.user_id == user_id, Budget.period == data.period,
        Budget.category_id == data.category_id, Budget.currency == data.currency,
    )
    for item in db.scalars(query):
        if item.id != exclude_id:
            raise HTTPException(409, "Ya existe un presupuesto para esa categoría, moneda y periodo")


@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(user: CurrentUser, db: DbSession):
    return db.scalars(select(Budget).where(Budget.user_id == user.id).order_by(Budget.id)).all()


@router.post("/budgets", response_model=BudgetOut, status_code=201)
def create_budget(data: BudgetIn, user: CurrentUser, db: DbSession):
    checked_category(db, user.id, data.category_id)
    ensure_unique(db, user.id, data)
    item = Budget(user_id=user.id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/budgets/{item_id}", response_model=BudgetOut)
def patch_budget(item_id: int, data: BudgetPatch, user: CurrentUser, db: DbSession):
    item = db.scalar(select(Budget).where(Budget.id == item_id, Budget.user_id == user.id))
    if item is None:
        raise HTTPException(404, "Presupuesto no encontrado")
    changes = data.model_dump(exclude_unset=True)
    values = {key: getattr(item, key) for key in BudgetIn.model_fields}
    values.update(changes)
    try:
        validated = BudgetIn.model_validate(values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    checked_category(db, user.id, validated.category_id)
    ensure_unique(db, user.id, validated, item_id)
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def actuals(db: DbSession, user_id: int, start: date, end: date):
    cutoff = min(end, user_today(db, user_id))
    return list(db.scalars(select(Transaction).where(
        Transaction.user_id == user_id, Transaction.status == "CLEARED",
        Transaction.type.in_(["INCOME", "EXPENSE"]),
        Transaction.date >= start, Transaction.date <= cutoff,
    )))


@router.get("/budget-status", response_model=list[BudgetStatus])
def budget_status(user: CurrentUser, db: DbSession, as_of: date | None = None):
    reference = as_of or user_today(db, user.id)
    accounts = {item.id: item for item in db.scalars(select(Account).where(Account.user_id == user.id))}
    categories = list(db.scalars(select(Category).where(Category.user_id == user.id)))
    children = {item.id: {item.id, *(child.id for child in categories if child.parent_id == item.id)} for item in categories}
    results = []
    for item in db.scalars(select(Budget).where(Budget.user_id == user.id).order_by(Budget.id)):
        period = window(db, user.id, item.period, reference)
        spent = None
        if period:
            spent = sum((
                movement.amount for movement in actuals(db, user.id, *period)
                if movement.type == "EXPENSE"
                and accounts[movement.source_account_id].currency == item.currency
                and (item.category_id is None or movement.category_id in children.get(item.category_id, {item.category_id}))
            ), Decimal("0"))
        results.append(BudgetStatus(
            id=item.id, category_id=item.category_id, period=item.period,
            currency=item.currency, amount=item.amount, active=item.active,
            start=period[0] if period else None, end=period[1] if period else None,
            spent=spent, remaining=item.amount - spent if spent is not None else None,
        ))
    return results


@router.get("/statistics", response_model=Statistics)
def statistics(user: CurrentUser, db: DbSession, period: Period = "MONTH", as_of: date | None = None):
    reference = as_of or user_today(db, user.id)
    dates = window(db, user.id, period, reference)
    if dates is None:
        raise HTTPException(422, "Configura una fuente de ingreso principal para usar ciclos de nómina")
    start, end = dates
    accounts = {item.id: item for item in db.scalars(select(Account).where(Account.user_id == user.id))}
    categories = {item.id: item for item in db.scalars(select(Category).where(Category.user_id == user.id))}
    income: dict[str, Decimal] = {}
    expense: dict[str, Decimal] = {}
    category_totals: dict[tuple[int | None, str], Decimal] = {}
    daily: dict[tuple[date, str], Decimal] = {}
    for movement in actuals(db, user.id, start, end):
        account_id = movement.destination_account_id if movement.type == "INCOME" else movement.source_account_id
        currency = accounts[account_id].currency
        if movement.type == "INCOME":
            income[currency] = income.get(currency, Decimal("0")) + movement.amount
            continue
        expense[currency] = expense.get(currency, Decimal("0")) + movement.amount
        key = movement.category_id, currency
        category_totals[key] = category_totals.get(key, Decimal("0")) + movement.amount
        daily_key = movement.date, currency
        daily[daily_key] = daily.get(daily_key, Decimal("0")) + movement.amount
    by_category = []
    for (category_id, currency), amount in category_totals.items():
        category = categories.get(category_id)
        parent = categories.get(category.parent_id) if category and category.parent_id else None
        name = f"{parent.name} / {category.name}" if parent else category.name if category else "Sin categoría"
        by_category.append(CategorySpend(category_id=category_id, name=name, currency=currency, amount=amount))
    return Statistics(
        period=period, start=start, end=end,
        income_by_currency=income, expense_by_currency=expense,
        expenses_by_category=sorted(by_category, key=lambda item: (item.currency, -item.amount, item.name)),
        daily_expenses=[DailySpend(date=day, currency=currency, amount=amount)
                        for (day, currency), amount in sorted(daily.items())],
    )
