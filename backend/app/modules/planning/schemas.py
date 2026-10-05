from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.http.schemas import ORMModel

Money = Decimal
PositiveMoney = Field(gt=0, max_digits=18, decimal_places=2)
DayRule = Literal["FIXED_DAY", "LAST_DAY_OF_MONTH", "FIRST_BUSINESS_DAY"]
Frequency = Literal["WEEKLY", "MONTHLY"]
ScheduleStatus = Literal["PLANNED", "PAID", "CANCELLED"]


class IncomeSourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount: Money = PositiveMoney
    account_id: int
    day_rule: DayRule
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    starts_on: date
    ends_on: date | None = None
    active: bool = True
    is_primary: bool = False

    @model_validator(mode="after")
    def validate_dates(self):
        if self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("La fecha final precede a la inicial")
        if self.day_rule == "FIXED_DAY" and self.day_of_month is None:
            raise ValueError("Indica el día de cobro")
        return self


class IncomeSourcePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    amount: Money | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    account_id: int | None = None
    day_rule: DayRule | None = None
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    starts_on: date | None = None
    ends_on: date | None = None
    active: bool | None = None
    is_primary: bool | None = None


class IncomeSourceOut(ORMModel, IncomeSourceIn):
    id: int


class RecurringExpenseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount: Money = PositiveMoney
    account_id: int
    category_id: int | None = None
    frequency: Frequency
    starts_on: date
    ends_on: date | None = None
    active: bool = True

    @model_validator(mode="after")
    def validate_dates(self):
        if self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("La fecha final precede a la inicial")
        return self


class RecurringExpensePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    amount: Money | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    account_id: int | None = None
    category_id: int | None = None
    frequency: Frequency | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    active: bool | None = None


class RecurringExpenseOut(ORMModel, RecurringExpenseIn):
    id: int


class ScheduledExpenseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount: Money = PositiveMoney
    account_id: int
    category_id: int | None = None
    due_date: date


class ScheduledExpensePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    amount: Money | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    account_id: int | None = None
    category_id: int | None = None
    due_date: date | None = None
    status: ScheduleStatus | None = None


class ScheduledExpenseOut(ORMModel, ScheduledExpenseIn):
    id: int
    status: ScheduleStatus
    transaction_id: int | None


class DebtIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    principal: Money = PositiveMoney
    installment_amount: Money = PositiveMoney
    account_id: int
    starts_on: date
    due_day: int = Field(ge=1, le=31)
    active: bool = True


class DebtPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    principal: Money | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    installment_amount: Money | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    account_id: int | None = None
    starts_on: date | None = None
    due_day: int | None = Field(default=None, ge=1, le=31)
    active: bool | None = None


class DebtOut(ORMModel, DebtIn):
    id: int
    remaining: Money


class OccurrenceLinkIn(BaseModel):
    due_date: date
    transaction_id: int


class TransactionLinkIn(BaseModel):
    transaction_id: int


class UpcomingEvent(BaseModel):
    date: date
    kind: Literal["INCOME", "RECURRING", "SCHEDULED", "DEBT"]
    source_id: int
    name: str
    amount: Money
    currency: str
    account_id: int
    overdue: bool = False


class PlanningLink(BaseModel):
    id: int
    kind: Literal["INCOME", "RECURRING", "SCHEDULED", "DEBT"]
    source_id: int
    transaction_id: int
    due_date: date | None = None
