from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import or_, select

from app.api.dependencies import CurrentUser, DbSession
from app.api.planning import upcoming
from app.application.calendar import income_dates
from app.application.finance import account_balances, user_today
from app.application.forecast import CashEvent, project
from app.infrastructure.models import Account, IncomeSource, Transaction

router = APIRouter(tags=["forecast"])


class SalaryCycle(BaseModel):
    available: bool
    source_id: int | None = None
    current_start: date | None = None
    current_end: date | None = None
    next_payday: date | None = None


class ForecastAccount(BaseModel):
    id: int
    name: str
    currency: str
    current: Decimal
    projected: Decimal


class ForecastEventOut(BaseModel):
    date: date
    account_id: int
    amount: Decimal
    label: str
    key: str


class ForecastDayOut(BaseModel):
    date: date
    balances: dict[int, Decimal]
    totals_by_currency: dict[str, Decimal]


class ForecastOut(BaseModel):
    start: date
    end: date
    salary_cycle: SalaryCycle
    accounts: list[ForecastAccount]
    events: list[ForecastEventOut]
    days: list[ForecastDayOut]
    minimum_until_payday_by_currency: dict[str, Decimal] | None


def salary_cycle(db: DbSession, user_id: int, today: date) -> SalaryCycle:
    source = db.scalar(select(IncomeSource).where(
        IncomeSource.user_id == user_id, IncomeSource.active == True, IncomeSource.is_primary == True
    ).order_by(IncomeSource.id))
    if source is None:
        return SalaryCycle(available=False)
    dates = income_dates(today - timedelta(days=80), today + timedelta(days=80),
                         source.day_rule, source.day_of_month, source.starts_on, source.ends_on)
    previous = max((day for day in dates if day <= today), default=None)
    next_payday = min((day for day in dates if day > today), default=None)
    return SalaryCycle(
        available=previous is not None and next_payday is not None,
        source_id=source.id,
        current_start=previous if previous and next_payday else None,
        current_end=next_payday - timedelta(days=1) if previous and next_payday else None,
        next_payday=next_payday,
    )


@router.get("/salary-cycles", response_model=SalaryCycle)
def read_salary_cycle(user: CurrentUser, db: DbSession):
    return salary_cycle(db, user.id, user_today(db, user.id))


@router.get("/forecast", response_model=ForecastOut)
def read_forecast(user: CurrentUser, db: DbSession, days: int = Query(90, ge=1, le=366)):
    start = user_today(db, user.id)
    end = start + timedelta(days=days - 1)
    accounts = list(db.scalars(select(Account).where(Account.user_id == user.id, Account.active == True).order_by(Account.id)))
    currencies = {account.id: account.currency for account in accounts}
    balances = account_balances(db, user.id, start)
    initial = {account.id: balances[account.id] for account in accounts}
    events: list[CashEvent] = []
    for item in upcoming(user, db, start, days):
        if item.account_id in initial:
            events.append(CashEvent(
                date=max(item.date, start), account_id=item.account_id,
                amount=item.amount if item.kind == "INCOME" else -item.amount,
                key=f"plan:{item.kind}:{item.source_id}:{item.date}", label=item.name,
            ))
    pending = db.scalars(select(Transaction).where(
        Transaction.user_id == user.id, Transaction.date <= end,
        or_(Transaction.status == "PENDING", Transaction.date > start),
    ).order_by(Transaction.date, Transaction.id))
    for item in pending:
        when = max(item.date, start)
        if item.source_account_id in initial:
            events.append(CashEvent(when, item.source_account_id, -item.amount, f"transaction:{item.id}:out", item.concept))
        if item.destination_account_id in initial:
            events.append(CashEvent(when, item.destination_account_id, item.amount, f"transaction:{item.id}:in", item.concept))
    timeline = project(initial, events, start, end)

    def totals(day) -> dict[str, Decimal]:
        result: dict[str, Decimal] = {}
        for account_id, value in day.balances.items():
            currency = currencies[account_id]
            result[currency] = result.get(currency, Decimal("0")) + value
        return result

    cycle = salary_cycle(db, user.id, start)
    until = [day for day in timeline if cycle.next_payday is not None and day.date < cycle.next_payday]
    minimum = None
    if until:
        minimum = {}
        for day in until:
            for currency, value in totals(day).items():
                minimum[currency] = min(minimum.get(currency, value), value)
    return ForecastOut(
        start=start, end=end, salary_cycle=cycle,
        accounts=[ForecastAccount(
            id=account.id, name=account.name, currency=account.currency,
            current=initial[account.id], projected=timeline[-1].balances[account.id],
        ) for account in accounts],
        events=[ForecastEventOut(date=event.date, account_id=event.account_id, amount=event.amount,
                                 label=event.label, key=event.key) for event in sorted(events, key=lambda event: (event.date, event.key))],
        days=[ForecastDayOut(date=day.date, balances=day.balances, totals_by_currency=totals(day)) for day in timeline],
        minimum_until_payday_by_currency=minimum,
    )
