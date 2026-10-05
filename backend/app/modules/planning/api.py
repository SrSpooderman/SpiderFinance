from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.http.dependencies import CurrentUser, DbSession
from app.modules.planning.schemas import (
    DebtIn, DebtOut, DebtPatch, IncomeSourceIn, IncomeSourceOut, IncomeSourcePatch,
    OccurrenceLinkIn, PlanningLink, RecurringExpenseIn, RecurringExpenseOut, RecurringExpensePatch,
    ScheduledExpenseIn, ScheduledExpenseOut, ScheduledExpensePatch, TransactionLinkIn, UpcomingEvent,
)
from app.modules.ledger.infrastructure import SqlLedgerStore
from app.modules.planning.application import upcoming as plan_upcoming
from app.modules.planning.infrastructure import SqlPlanningReader
from app.modules.planning.write_application import Planning
from app.modules.planning.write_infrastructure import SqlPlanningStore
from app.modules.savings.infrastructure import SqlSavingsStore

router = APIRouter(tags=["planning"])


def user_today(db: DbSession, user_id: int) -> date:
    return SqlLedgerStore(db).today(user_id)


def planning(db: DbSession) -> Planning:
    ledger = SqlLedgerStore(db)
    return Planning(SqlPlanningStore(db, ledger), SqlSavingsStore(db, ledger))


def validated_patch(service: Planning, kind: str, user_id: int, item_id: int, data, schema):
    current = service.get(kind, user_id, item_id)
    changes = data.model_dump(exclude_unset=True)
    values = {key: current[key] for key in schema.model_fields}
    values.update(changes)
    try:
        validated = schema.model_validate(values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return validated.model_dump(), changes


@router.get("/planning-links", response_model=list[PlanningLink])
def list_planning_links(user: CurrentUser, db: DbSession):
    return planning(db).links(user.id)


@router.get("/income-sources", response_model=list[IncomeSourceOut])
def list_income_sources(user: CurrentUser, db: DbSession):
    return planning(db).list("income", user.id)


@router.post("/income-sources", response_model=IncomeSourceOut, status_code=201)
def create_income_source(data: IncomeSourceIn, user: CurrentUser, db: DbSession):
    return planning(db).create_income(user.id, data.model_dump())


@router.patch("/income-sources/{item_id}", response_model=IncomeSourceOut)
def patch_income_source(item_id: int, data: IncomeSourcePatch, user: CurrentUser, db: DbSession):
    service = planning(db)
    values, changes = validated_patch(service, "income", user.id, item_id, data, IncomeSourceIn)
    return service.update_income(user.id, item_id, values, changes)


@router.delete("/income-sources/{item_id}", status_code=204)
def delete_income_source(item_id: int, user: CurrentUser, db: DbSession):
    planning(db).delete_income(user.id, item_id)


@router.post("/income-sources/{item_id}/receipts", status_code=201)
def link_income_receipt(item_id: int, data: OccurrenceLinkIn, user: CurrentUser, db: DbSession):
    return planning(db).link_income(user.id, item_id, data.due_date, data.transaction_id)


@router.delete("/income-sources/{item_id}/receipts/{link_id}", status_code=204)
def unlink_income_receipt(item_id: int, link_id: int, user: CurrentUser, db: DbSession):
    planning(db).unlink_income(user.id, item_id, link_id)


@router.get("/recurring-expenses", response_model=list[RecurringExpenseOut])
def list_recurring_expenses(user: CurrentUser, db: DbSession):
    return planning(db).list("recurring", user.id)


@router.post("/recurring-expenses", response_model=RecurringExpenseOut, status_code=201)
def create_recurring_expense(data: RecurringExpenseIn, user: CurrentUser, db: DbSession):
    return planning(db).create_recurring(user.id, data.model_dump())


@router.patch("/recurring-expenses/{item_id}", response_model=RecurringExpenseOut)
def patch_recurring_expense(item_id: int, data: RecurringExpensePatch, user: CurrentUser, db: DbSession):
    service = planning(db)
    values, changes = validated_patch(service, "recurring", user.id, item_id, data, RecurringExpenseIn)
    return service.update_recurring(user.id, item_id, values, changes)


@router.delete("/recurring-expenses/{item_id}", status_code=204)
def delete_recurring_expense(item_id: int, user: CurrentUser, db: DbSession):
    planning(db).delete_recurring(user.id, item_id)


@router.post("/recurring-expenses/{item_id}/payments", status_code=201)
def link_recurring_payment(item_id: int, data: OccurrenceLinkIn, user: CurrentUser, db: DbSession):
    return planning(db).link_recurring(user.id, item_id, data.due_date, data.transaction_id)


@router.delete("/recurring-expenses/{item_id}/payments/{link_id}", status_code=204)
def unlink_recurring_payment(item_id: int, link_id: int, user: CurrentUser, db: DbSession):
    planning(db).unlink_recurring(user.id, item_id, link_id)


@router.get("/scheduled-expenses", response_model=list[ScheduledExpenseOut])
def list_scheduled_expenses(user: CurrentUser, db: DbSession):
    return planning(db).list("scheduled", user.id)


@router.post("/scheduled-expenses", response_model=ScheduledExpenseOut, status_code=201)
def create_scheduled_expense(data: ScheduledExpenseIn, user: CurrentUser, db: DbSession):
    return planning(db).create_scheduled(user.id, data.model_dump())


@router.patch("/scheduled-expenses/{item_id}", response_model=ScheduledExpenseOut)
def patch_scheduled_expense(item_id: int, data: ScheduledExpensePatch, user: CurrentUser, db: DbSession):
    service = planning(db)
    values, changes = validated_patch(service, "scheduled", user.id, item_id, data, ScheduledExpenseIn)
    return service.update_scheduled(user.id, item_id, values, changes)


@router.delete("/scheduled-expenses/{item_id}", status_code=204)
def delete_scheduled_expense(item_id: int, user: CurrentUser, db: DbSession):
    planning(db).delete_scheduled(user.id, item_id)


@router.post("/scheduled-expenses/{item_id}/pay", response_model=ScheduledExpenseOut)
def pay_scheduled_expense(item_id: int, data: TransactionLinkIn, user: CurrentUser, db: DbSession):
    return planning(db).pay_scheduled(user.id, item_id, data.transaction_id)


@router.delete("/scheduled-expenses/{item_id}/pay", response_model=ScheduledExpenseOut)
def unpay_scheduled_expense(item_id: int, user: CurrentUser, db: DbSession):
    return planning(db).unpay_scheduled(user.id, item_id)


@router.get("/debts", response_model=list[DebtOut])
def list_debts(user: CurrentUser, db: DbSession):
    return planning(db).debts(user.id)


@router.post("/debts", response_model=DebtOut, status_code=201)
def create_debt(data: DebtIn, user: CurrentUser, db: DbSession):
    return planning(db).create_debt(user.id, data.model_dump())


@router.patch("/debts/{item_id}", response_model=DebtOut)
def patch_debt(item_id: int, data: DebtPatch, user: CurrentUser, db: DbSession):
    service = planning(db)
    values, changes = validated_patch(service, "debt", user.id, item_id, data, DebtIn)
    return service.update_debt(user.id, item_id, values, changes)


@router.delete("/debts/{item_id}", status_code=204)
def delete_debt(item_id: int, user: CurrentUser, db: DbSession):
    planning(db).delete_debt(user.id, item_id)


@router.post("/debts/{item_id}/payments", response_model=DebtOut, status_code=201)
def pay_debt(item_id: int, data: TransactionLinkIn, user: CurrentUser, db: DbSession):
    return planning(db).pay_debt(user.id, item_id, data.transaction_id)


@router.delete("/debts/{item_id}/payments/{link_id}", response_model=DebtOut)
def unpay_debt(item_id: int, link_id: int, user: CurrentUser, db: DbSession):
    return planning(db).unpay_debt(user.id, item_id, link_id)


@router.get("/upcoming", response_model=list[UpcomingEvent])
def upcoming(user: CurrentUser, db: DbSession, date_from: date | None = None,
             days: int = Query(90, ge=1, le=366)):
    return plan_upcoming(SqlPlanningReader(db), user.id, date_from or user_today(db, user.id), days)
