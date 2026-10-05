from fastapi import APIRouter, HTTPException

from app.http.dependencies import CurrentUser, DbSession
from app.modules.savings.schemas import (
    ContributionIn, ContributionOut, GoalIn, GoalOut, GoalPatch,
    ReleaseIn, ReservationIn, ReservationOut, SavingsRecommendation,
    SavingsRuleIn, SavingsRuleOut, SavingsRulePatch,
)
from app.modules.savings.application import Savings
from app.modules.savings.infrastructure import SqlSavingsStore
from app.modules.ledger.infrastructure import SqlLedgerStore

router = APIRouter(tags=["savings"])


def savings(db: DbSession) -> Savings:
    return Savings(SqlSavingsStore(db, SqlLedgerStore(db)))


@router.get("/goals", response_model=list[GoalOut])
def list_goals(user: CurrentUser, db: DbSession):
    return savings(db).goals(user.id)


@router.post("/goals", response_model=GoalOut, status_code=201)
def create_goal(data: GoalIn, user: CurrentUser, db: DbSession):
    return savings(db).create_goal(user.id, data.model_dump())


@router.patch("/goals/{item_id}", response_model=GoalOut)
def patch_goal(item_id: int, data: GoalPatch, user: CurrentUser, db: DbSession):
    service = savings(db)
    current = service.goal(user.id, item_id)
    changes = data.model_dump(exclude_unset=True)
    values = {key: current[key] for key in GoalIn.model_fields}
    values.update(changes)
    try:
        validated = GoalIn.model_validate(values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return service.update_goal(user.id, item_id, validated.model_dump(), changes)


@router.get("/reservations", response_model=list[ReservationOut])
def list_reservations(user: CurrentUser, db: DbSession):
    return savings(db).reservations(user.id)


@router.post("/reservations", response_model=ReservationOut, status_code=201)
def create_reservation(data: ReservationIn, user: CurrentUser, db: DbSession):
    return savings(db).reserve(user.id, data.account_id, data.goal_id, data.amount, data.date, data.notes)


@router.post("/goals/{item_id}/contributions", response_model=ReservationOut, status_code=201)
def contribute_to_goal(item_id: int, data: ContributionIn, user: CurrentUser, db: DbSession):
    return savings(db).reserve(user.id, data.account_id, item_id, data.amount, data.date, data.notes)


@router.post("/reservations/{item_id}/release", response_model=ReservationOut)
def release_reservation(item_id: int, data: ReleaseIn, user: CurrentUser, db: DbSession):
    return savings(db).release(user.id, item_id, data.amount, data.date, data.notes)


@router.get("/goal-contributions", response_model=list[ContributionOut])
def list_contributions(user: CurrentUser, db: DbSession):
    return savings(db).contributions(user.id)


@router.get("/savings-rules", response_model=list[SavingsRuleOut])
def list_rules(user: CurrentUser, db: DbSession):
    return savings(db).rules(user.id)


@router.post("/savings-rules", response_model=SavingsRuleOut, status_code=201)
def create_rule(data: SavingsRuleIn, user: CurrentUser, db: DbSession):
    return savings(db).create_rule(user.id, data.model_dump())


@router.patch("/savings-rules/{item_id}", response_model=SavingsRuleOut)
def patch_rule(item_id: int, data: SavingsRulePatch, user: CurrentUser, db: DbSession):
    service = savings(db)
    current = service.rule(user.id, item_id)
    changes = data.model_dump(exclude_unset=True)
    values = {key: current[key] for key in SavingsRuleIn.model_fields}
    values.update(changes)
    try:
        validated = SavingsRuleIn.model_validate(values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return service.update_rule(user.id, item_id, validated.model_dump(), changes)


@router.get("/savings-recommendations", response_model=SavingsRecommendation)
def savings_recommendations(user: CurrentUser, db: DbSession):
    return savings(db).recommendations(user.id)
