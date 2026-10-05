from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.http.schemas import ORMModel


class PositionIn(BaseModel):
    account_id: int
    name: str = Field(min_length=1, max_length=120)
    symbol: str | None = Field(default=None, max_length=32)
    units: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    cost_basis: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    market_value: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    valued_on: date


class PositionPatch(BaseModel):
    account_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    symbol: str | None = Field(default=None, max_length=32)
    units: Decimal | None = Field(default=None, gt=0, max_digits=24, decimal_places=8)
    cost_basis: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    market_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    valued_on: date | None = None


class PositionOut(ORMModel, PositionIn):
    id: int


# The original module name keeps the published OpenAPI component key stable.
class ContributionIn(BaseModel):
    __module__ = "app.api.investment_schemas"
    transaction_id: int


class ContributionOut(ORMModel):
    __module__ = "app.api.investment_schemas"
    id: int
    account_id: int
    transaction_id: int


class NetWorthCurrency(BaseModel):
    currency: str
    assets: Decimal
    liabilities: Decimal
    net_worth: Decimal


class NetWorthAccount(BaseModel):
    id: int
    name: str
    type: str
    currency: str
    book_balance: Decimal
    position_value: Decimal
    uninvested_cash: Decimal
    asset_value: Decimal


class NetWorthOut(BaseModel):
    date: date
    currencies: list[NetWorthCurrency]
    accounts: list[NetWorthAccount]


class SnapshotOut(ORMModel):
    id: int
    date: date
    currency: str
    assets: Decimal
    liabilities: Decimal
    net_worth: Decimal
