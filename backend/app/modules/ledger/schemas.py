from datetime import date as Date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.http.schemas import ORMModel
from app.modules.ledger.types import AccountType, TransactionStatus, TransactionType


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: AccountType
    institution: str | None = Field(default=None, max_length=120)
    initial_balance: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")
    active: bool = True
    notes: str | None = None


class AccountPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    type: AccountType | None = None
    institution: str | None = Field(default=None, max_length=120)
    initial_balance: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    active: bool | None = None
    notes: str | None = None


class AccountOut(ORMModel):
    id: int
    name: str
    type: AccountType
    institution: str | None
    initial_balance: Decimal
    currency: str
    active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime
    balance: Decimal | None = None


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = None


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: int | None = None


class CategoryOut(ORMModel):
    id: int
    name: str
    parent_id: int | None


class TransactionIn(BaseModel):
    date: Date
    type: TransactionType
    source_account_id: int | None = None
    destination_account_id: int | None = None
    category_id: int | None = None
    concept: str = Field(min_length=1, max_length=240)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    payment_method: str | None = Field(default=None, max_length=50)
    is_fixed: bool = False
    is_necessary: bool = False
    notes: str | None = None
    status: TransactionStatus = TransactionStatus.CLEARED


class TransactionPatch(BaseModel):
    date: Date | None = None
    type: TransactionType | None = None
    source_account_id: int | None = None
    destination_account_id: int | None = None
    category_id: int | None = None
    concept: str | None = Field(default=None, min_length=1, max_length=240)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    payment_method: str | None = Field(default=None, max_length=50)
    is_fixed: bool | None = None
    is_necessary: bool | None = None
    notes: str | None = None
    status: TransactionStatus | None = None


class TransactionOut(ORMModel):
    id: int
    date: Date
    type: TransactionType
    source_account_id: int | None
    destination_account_id: int | None
    category_id: int | None
    concept: str
    amount: Decimal
    payment_method: str | None
    is_fixed: bool
    is_necessary: bool
    notes: str | None
    status: TransactionStatus
    reconciliation: bool
    created_at: datetime
    updated_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    page_size: int


class ReconcileIn(BaseModel):
    date: Date
    observed_balance: Decimal = Field(max_digits=18, decimal_places=2)
    notes: str | None = None


class ReconcileOut(BaseModel):
    difference: Decimal
    transaction: TransactionOut | None
