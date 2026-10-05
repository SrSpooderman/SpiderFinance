from datetime import date
from decimal import Decimal

from pydantic import BaseModel


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
    reserved_by_currency: dict[str, Decimal]
    available_now_by_currency: dict[str, Decimal]
    minimum_until_payday_by_currency: dict[str, Decimal] | None


