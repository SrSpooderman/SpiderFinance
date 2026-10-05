from decimal import Decimal

from fastapi import APIRouter

from app.http.dependencies import CurrentUser, DbSession
from app.infrastructure.ledger_policies import SqlLedgerPolicies
from app.modules.ledger.schemas import AccountIn, AccountOut, AccountPatch, ReconcileIn, ReconcileOut
from app.modules.ledger.application import Ledger
from app.modules.ledger.infrastructure import SqlLedgerStore

router = APIRouter(prefix="/accounts", tags=["accounts"])


def ledger(db: DbSession) -> Ledger:
    return Ledger(SqlLedgerStore(db), SqlLedgerPolicies(db))


@router.get("", response_model=list[AccountOut])
def list_accounts(user: CurrentUser, db: DbSession):
    return ledger(db).list_accounts(user.id)


@router.post("", response_model=AccountOut, status_code=201)
def create_account(data: AccountIn, user: CurrentUser, db: DbSession):
    return ledger(db).create_account(user.id, data.model_dump())


@router.get("/{account_id}", response_model=AccountOut)
def read_account(account_id: int, user: CurrentUser, db: DbSession):
    return ledger(db).read_account(user.id, account_id)


@router.get("/{account_id}/balance", response_model=dict[str, Decimal])
def read_balance(account_id: int, user: CurrentUser, db: DbSession):
    return {"balance": ledger(db).balance(user.id, account_id)}


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, data: AccountPatch, user: CurrentUser, db: DbSession):
    return ledger(db).update_account(user.id, account_id, data.model_dump(exclude_unset=True))


@router.post("/{account_id}/reconcile", response_model=ReconcileOut)
def reconcile(account_id: int, data: ReconcileIn, user: CurrentUser, db: DbSession):
    return ledger(db).reconcile(user.id, account_id, data.date, data.observed_balance, data.notes)
