from fastapi import APIRouter, HTTPException

from app.http.dependencies import CurrentUser, DbSession
from app.modules.investments.schemas import (
    ContributionIn, ContributionOut, NetWorthOut, PositionIn, PositionOut, PositionPatch, SnapshotOut,
)
from app.modules.investments.application import Investments
from app.modules.investments.infrastructure import SqlInvestmentStore
from app.modules.ledger.infrastructure import SqlLedgerStore
from app.modules.planning.infrastructure import SqlPlanningReader

router = APIRouter(tags=["investments"])


def investments(db: DbSession) -> Investments:
    return Investments(SqlInvestmentStore(db, SqlLedgerStore(db), SqlPlanningReader(db)))


@router.get("/investments/positions", response_model=list[PositionOut])
def list_positions(user: CurrentUser, db: DbSession):
    return investments(db).positions(user.id)


@router.post("/investments/positions", response_model=PositionOut, status_code=201)
def create_position(data: PositionIn, user: CurrentUser, db: DbSession):
    return investments(db).create_position(user.id, data.model_dump())


@router.patch("/investments/positions/{item_id}", response_model=PositionOut)
def patch_position(item_id: int, data: PositionPatch, user: CurrentUser, db: DbSession):
    service = investments(db)
    current = service.position(user.id, item_id)
    changes = data.model_dump(exclude_unset=True)
    values = {key: current[key] for key in PositionIn.model_fields}
    values.update(changes)
    try:
        validated = PositionIn.model_validate(values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return service.update_position(user.id, item_id, validated.model_dump(), changes)


@router.delete("/investments/positions/{item_id}", status_code=204)
def delete_position(item_id: int, user: CurrentUser, db: DbSession):
    investments(db).delete_position(user.id, item_id)


@router.get("/investments/contributions", response_model=list[ContributionOut])
def list_contributions(user: CurrentUser, db: DbSession):
    return investments(db).contributions(user.id)


@router.post("/investments/contributions", response_model=ContributionOut, status_code=201)
def link_contribution(data: ContributionIn, user: CurrentUser, db: DbSession):
    return investments(db).link_contribution(user.id, data.transaction_id)


@router.delete("/investments/contributions/{item_id}", status_code=204)
def unlink_contribution(item_id: int, user: CurrentUser, db: DbSession):
    investments(db).unlink_contribution(user.id, item_id)


@router.get("/net-worth", response_model=NetWorthOut)
def read_net_worth(user: CurrentUser, db: DbSession):
    return investments(db).net_worth(user.id)


@router.get("/net-worth/snapshots", response_model=list[SnapshotOut])
def list_snapshots(user: CurrentUser, db: DbSession):
    return investments(db).snapshots(user.id)


@router.post("/net-worth/snapshots", response_model=list[SnapshotOut], status_code=201)
def create_snapshot(user: CurrentUser, db: DbSession):
    return investments(db).create_snapshot(user.id)
