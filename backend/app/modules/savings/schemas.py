from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.http.schemas import ORMModel


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    priority: int = Field(default=1, ge=1, le=100)
    due_date: date | None = None
    active: bool = True


class GoalPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    target_amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    priority: int | None = Field(default=None, ge=1, le=100)
    due_date: date | None = None
    active: bool | None = None


class GoalOut(ORMModel, GoalIn):
    id: int
    funded: Decimal


class ReservationIn(BaseModel):
    account_id: int
    goal_id: int | None = None
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    date: date
    notes: str | None = None


# The original module name keeps the published OpenAPI component key stable.
class ContributionIn(BaseModel):
    __module__ = "app.api.savings_schemas"
    account_id: int
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    date: date
    notes: str | None = None


class ReleaseIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    date: date
    notes: str | None = None


class ReservationOut(ORMModel):
    id: int
    account_id: int
    goal_id: int | None
    amount: Decimal


class ContributionOut(ORMModel):
    __module__ = "app.api.savings_schemas"
    id: int
    goal_id: int
    account_id: int
    date: date
    amount: Decimal
    notes: str | None


class SavingsRuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    income_source_id: int
    mode: Literal["PERCENT", "FIXED"]
    value: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    active: bool = True


class SavingsRulePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    income_source_id: int | None = None
    mode: Literal["PERCENT", "FIXED"] | None = None
    value: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    active: bool | None = None


class SavingsRuleOut(ORMModel, SavingsRuleIn):
    id: int


class RuleSuggestion(BaseModel):
    rule_id: int
    source_id: int
    currency: str
    amount: Decimal


class GoalAllocation(BaseModel):
    goal_id: int
    currency: str
    amount: Decimal


class SavingsRecommendation(BaseModel):
    rules: list[RuleSuggestion]
    allocations: list[GoalAllocation]
    unallocated_by_currency: dict[str, Decimal]
