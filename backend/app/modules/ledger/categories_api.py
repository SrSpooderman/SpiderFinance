from fastapi import APIRouter

from app.http.dependencies import CurrentUser, DbSession
from app.infrastructure.ledger_policies import SqlLedgerPolicies
from app.modules.ledger.schemas import CategoryIn, CategoryOut, CategoryPatch
from app.modules.ledger.application import Ledger
from app.modules.ledger.infrastructure import SqlLedgerStore

router = APIRouter(prefix="/categories", tags=["categories"])


def ledger(db: DbSession) -> Ledger:
    return Ledger(SqlLedgerStore(db), SqlLedgerPolicies(db))


@router.get("", response_model=list[CategoryOut])
def list_categories(user: CurrentUser, db: DbSession):
    return ledger(db).list_categories(user.id)


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryIn, user: CurrentUser, db: DbSession):
    return ledger(db).create_category(user.id, data.model_dump())


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryPatch, user: CurrentUser, db: DbSession):
    return ledger(db).update_category(user.id, category_id, data.model_dump(exclude_unset=True))


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, user: CurrentUser, db: DbSession) -> None:
    ledger(db).delete_category(user.id, category_id)
