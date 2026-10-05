from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.http.dependencies import CurrentUser, DbSession
from app.http.schemas import ORMModel
from app.modules.budgets.application import Budgets
from app.modules.budgets.infrastructure import SqlBudgetStore
from app.modules.ledger.infrastructure import SqlLedgerStore
from app.modules.planning.infrastructure import SqlPlanningReader

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


def budgets(db: DbSession) -> Budgets:
    return Budgets(SqlBudgetStore(db, SqlLedgerStore(db)), SqlPlanningReader(db))


@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(user: CurrentUser, db: DbSession):
    return budgets(db).list(user.id)


@router.post("/budgets", response_model=BudgetOut, status_code=201)
def create_budget(data: BudgetIn, user: CurrentUser, db: DbSession):
    return budgets(db).create(user.id, data.model_dump())


@router.patch("/budgets/{item_id}", response_model=BudgetOut)
def patch_budget(item_id: int, data: BudgetPatch, user: CurrentUser, db: DbSession):
    service = budgets(db)
    current = service.get(user.id, item_id)
    changes = data.model_dump(exclude_unset=True)
    values = {key: current[key] for key in BudgetIn.model_fields}
    values.update(changes)
    try:
        validated = BudgetIn.model_validate(values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return service.update(user.id, item_id, validated.model_dump(), changes)


@router.get("/budget-status", response_model=list[BudgetStatus])
def budget_status(user: CurrentUser, db: DbSession, as_of: date | None = None):
    return budgets(db).status(user.id, as_of)


@router.get("/statistics", response_model=Statistics)
def statistics(user: CurrentUser, db: DbSession, period: Period = "MONTH", as_of: date | None = None):
    return budgets(db).statistics(user.id, period, as_of)
