from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query

from app.http.dependencies import CurrentUser, DbSession
from app.infrastructure.ledger_policies import SqlLedgerPolicies
from app.modules.ledger.schemas import TransactionIn, TransactionOut, TransactionPage, TransactionPatch
from app.modules.ledger.types import TransactionType
from app.modules.ledger.application import Ledger
from app.modules.ledger.infrastructure import SqlLedgerStore

router = APIRouter(prefix="/transactions", tags=["transactions"])


def ledger(db: DbSession) -> Ledger:
    return Ledger(SqlLedgerStore(db), SqlLedgerPolicies(db))


@router.get("", response_model=TransactionPage)
def list_transactions(
    user: CurrentUser, db: DbSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    date_from: date | None = None, date_to: date | None = None,
    account_id: int | None = None, type: TransactionType | None = None,
    category_id: int | None = None, search: str | None = None,
    min_amount: Decimal | None = Query(None, ge=0), max_amount: Decimal | None = Query(None, ge=0),
    is_fixed: bool | None = None, is_necessary: bool | None = None,
):
    filters = dict(date_from=date_from, date_to=date_to, account_id=account_id, type=type,
                   category_id=category_id, search=search, min_amount=min_amount, max_amount=max_amount,
                   is_fixed=is_fixed, is_necessary=is_necessary)
    return ledger(db).list_transactions(user.id, filters, page, page_size)


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionIn, user: CurrentUser, db: DbSession):
    return ledger(db).create_transaction(user.id, data.model_dump())


@router.get("/{transaction_id}", response_model=TransactionOut)
def read_transaction(transaction_id: int, user: CurrentUser, db: DbSession):
    return ledger(db).transaction(user.id, transaction_id)


@router.patch("/{transaction_id}", response_model=TransactionOut)
def update_transaction(transaction_id: int, data: TransactionPatch, user: CurrentUser, db: DbSession):
    return ledger(db).update_transaction(user.id, transaction_id, data.model_dump(exclude_unset=True),
                                         tuple(TransactionIn.model_fields))


@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, user: CurrentUser, db: DbSession) -> None:
    ledger(db).delete_transaction(user.id, transaction_id)
