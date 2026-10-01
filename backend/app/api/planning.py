from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, DbSession
from app.api.planning_schemas import (
    DebtIn, DebtOut, DebtPatch, IncomeSourceIn, IncomeSourceOut, IncomeSourcePatch,
    OccurrenceLinkIn, PlanningLink, RecurringExpenseIn, RecurringExpenseOut, RecurringExpensePatch,
    ScheduledExpenseIn, ScheduledExpenseOut, ScheduledExpensePatch, TransactionLinkIn, UpcomingEvent,
)
from app.application.calendar import income_dates, monthly_dates, recurring_dates
from app.application.finance import get_account, get_category, user_today
from app.infrastructure.models import (
    Account, Debt, DebtPayment, IncomeReceipt, IncomeSource, RecurringExpense,
    RecurringPayment, ScheduledExpense, Transaction,
)

router = APIRouter(tags=["planning"])


@router.get("/planning-links", response_model=list[PlanningLink])
def list_planning_links(user: CurrentUser, db: DbSession):
    links: list[PlanningLink] = []
    for item in db.scalars(select(IncomeReceipt).where(IncomeReceipt.user_id == user.id)):
        links.append(PlanningLink(id=item.id, kind="INCOME", source_id=item.source_id, transaction_id=item.transaction_id, due_date=item.due_date))
    for item in db.scalars(select(RecurringPayment).where(RecurringPayment.user_id == user.id)):
        links.append(PlanningLink(id=item.id, kind="RECURRING", source_id=item.expense_id, transaction_id=item.transaction_id, due_date=item.due_date))
    for item in db.scalars(select(ScheduledExpense).where(ScheduledExpense.user_id == user.id, ScheduledExpense.status == "PAID")):
        links.append(PlanningLink(id=item.id, kind="SCHEDULED", source_id=item.id, transaction_id=item.transaction_id, due_date=item.due_date))
    for item in db.scalars(select(DebtPayment).where(DebtPayment.user_id == user.id)):
        links.append(PlanningLink(id=item.id, kind="DEBT", source_id=item.debt_id, transaction_id=item.transaction_id))
    return links


def owned(db: Session, model: type, user_id: int, item_id: int):
    item = db.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
    if item is None:
        raise HTTPException(404, "Elemento no encontrado")
    return item


def checked_account(db: Session, user_id: int, account_id: int) -> Account:
    account = get_account(db, user_id, account_id)
    if not account.active:
        raise HTTPException(422, "La cuenta está inactiva")
    return account


def validate_refs(db: Session, user_id: int, account_id: int, category_id: int | None = None) -> None:
    checked_account(db, user_id, account_id)
    if category_id is not None:
        get_category(db, user_id, category_id)


def update_model(db: Session, item, patch, schema, user_id: int, *, category: bool = False):
    changes = patch.model_dump(exclude_unset=True)
    fields = schema.model_fields.keys()
    values = {field: getattr(item, field) for field in fields}
    values.update(changes)
    try:
        validated = schema.model_validate(values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if validated.account_id != item.account_id:
        checked_account(db, user_id, validated.account_id)
    else:
        get_account(db, user_id, validated.account_id)
    if category and validated.category_id is not None:
        get_category(db, user_id, validated.category_id)
    for key, value in changes.items():
        setattr(item, key, value)
    return item


def set_primary(db: Session, user_id: int, selected: IncomeSource) -> None:
    if selected.active and selected.is_primary:
        for other in db.scalars(select(IncomeSource).where(
            IncomeSource.user_id == user_id, IncomeSource.id != selected.id, IncomeSource.is_primary == True
        )):
            other.is_primary = False


def linked_transaction(db: Session, user_id: int, transaction_id: int, kind: str, account_id: int) -> Transaction:
    movement = owned(db, Transaction, user_id, transaction_id)
    if movement.type != kind or movement.status != "CLEARED":
        raise HTTPException(422, "El movimiento debe estar confirmado y tener el tipo correcto")
    if movement.date > user_today(db, user_id):
        raise HTTPException(422, "Un movimiento futuro todavía no puede liquidar una obligación")
    if (movement.destination_account_id if kind == "INCOME" else movement.source_account_id) != account_id:
        raise HTTPException(422, "La cuenta del movimiento no coincide con la planificación")
    for model in (IncomeReceipt, RecurringPayment, ScheduledExpense, DebtPayment):
        if db.scalar(select(model.id).where(model.transaction_id == transaction_id)):
            raise HTTPException(409, "El movimiento ya está vinculado a otra planificación")
    return movement


def debt_remaining(db: Session, debt: Debt) -> Decimal:
    paid = db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0))
        .join(DebtPayment, DebtPayment.transaction_id == Transaction.id)
        .where(DebtPayment.debt_id == debt.id, DebtPayment.user_id == debt.user_id)) or Decimal("0")
    return debt.principal - Decimal(paid)


def debt_out(db: Session, debt: Debt) -> DebtOut:
    values = {field: getattr(debt, field) for field in DebtIn.model_fields}
    return DebtOut(id=debt.id, remaining=debt_remaining(db, debt), **values)


@router.get("/income-sources", response_model=list[IncomeSourceOut])
def list_income_sources(user: CurrentUser, db: DbSession):
    return db.scalars(select(IncomeSource).where(IncomeSource.user_id == user.id).order_by(IncomeSource.id)).all()


@router.post("/income-sources", response_model=IncomeSourceOut, status_code=201)
def create_income_source(data: IncomeSourceIn, user: CurrentUser, db: DbSession):
    validate_refs(db, user.id, data.account_id)
    item = IncomeSource(user_id=user.id, **data.model_dump())
    db.add(item)
    db.flush()
    set_primary(db, user.id, item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/income-sources/{item_id}", response_model=IncomeSourceOut)
def patch_income_source(item_id: int, data: IncomeSourcePatch, user: CurrentUser, db: DbSession):
    item = owned(db, IncomeSource, user.id, item_id)
    update_model(db, item, data, IncomeSourceIn, user.id)
    set_primary(db, user.id, item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/income-sources/{item_id}/receipts", status_code=201)
def link_income_receipt(item_id: int, data: OccurrenceLinkIn, user: CurrentUser, db: DbSession):
    item = owned(db, IncomeSource, user.id, item_id)
    if data.due_date not in income_dates(data.due_date, data.due_date, item.day_rule, item.day_of_month, item.starts_on, item.ends_on):
        raise HTTPException(422, "La fecha no es un vencimiento de esta fuente")
    linked_transaction(db, user.id, data.transaction_id, "INCOME", item.account_id)
    if db.scalar(select(IncomeReceipt.id).where(IncomeReceipt.source_id == item.id, IncomeReceipt.due_date == data.due_date)):
        raise HTTPException(409, "Este cobro ya está vinculado")
    link = IncomeReceipt(user_id=user.id, source_id=item.id, due_date=data.due_date, transaction_id=data.transaction_id)
    db.add(link)
    db.commit()
    return {"id": link.id}


@router.delete("/income-sources/{item_id}/receipts/{link_id}", status_code=204)
def unlink_income_receipt(item_id: int, link_id: int, user: CurrentUser, db: DbSession):
    owned(db, IncomeSource, user.id, item_id)
    link = owned(db, IncomeReceipt, user.id, link_id)
    if link.source_id != item_id:
        raise HTTPException(404, "Vínculo no encontrado")
    db.delete(link)
    db.commit()


@router.get("/recurring-expenses", response_model=list[RecurringExpenseOut])
def list_recurring_expenses(user: CurrentUser, db: DbSession):
    return db.scalars(select(RecurringExpense).where(RecurringExpense.user_id == user.id).order_by(RecurringExpense.id)).all()


@router.post("/recurring-expenses", response_model=RecurringExpenseOut, status_code=201)
def create_recurring_expense(data: RecurringExpenseIn, user: CurrentUser, db: DbSession):
    validate_refs(db, user.id, data.account_id, data.category_id)
    item = RecurringExpense(user_id=user.id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/recurring-expenses/{item_id}", response_model=RecurringExpenseOut)
def patch_recurring_expense(item_id: int, data: RecurringExpensePatch, user: CurrentUser, db: DbSession):
    item = owned(db, RecurringExpense, user.id, item_id)
    update_model(db, item, data, RecurringExpenseIn, user.id, category=True)
    db.commit()
    db.refresh(item)
    return item


@router.post("/recurring-expenses/{item_id}/payments", status_code=201)
def link_recurring_payment(item_id: int, data: OccurrenceLinkIn, user: CurrentUser, db: DbSession):
    item = owned(db, RecurringExpense, user.id, item_id)
    if data.due_date not in recurring_dates(data.due_date, data.due_date, item.frequency, item.starts_on, item.ends_on):
        raise HTTPException(422, "La fecha no es un vencimiento recurrente")
    linked_transaction(db, user.id, data.transaction_id, "EXPENSE", item.account_id)
    if db.scalar(select(RecurringPayment.id).where(RecurringPayment.expense_id == item.id, RecurringPayment.due_date == data.due_date)):
        raise HTTPException(409, "Este vencimiento ya está vinculado")
    link = RecurringPayment(user_id=user.id, expense_id=item.id, due_date=data.due_date, transaction_id=data.transaction_id)
    db.add(link)
    db.commit()
    return {"id": link.id}


@router.delete("/recurring-expenses/{item_id}/payments/{link_id}", status_code=204)
def unlink_recurring_payment(item_id: int, link_id: int, user: CurrentUser, db: DbSession):
    owned(db, RecurringExpense, user.id, item_id)
    link = owned(db, RecurringPayment, user.id, link_id)
    if link.expense_id != item_id:
        raise HTTPException(404, "Vínculo no encontrado")
    db.delete(link)
    db.commit()


@router.get("/scheduled-expenses", response_model=list[ScheduledExpenseOut])
def list_scheduled_expenses(user: CurrentUser, db: DbSession):
    return db.scalars(select(ScheduledExpense).where(ScheduledExpense.user_id == user.id).order_by(ScheduledExpense.due_date)).all()


@router.post("/scheduled-expenses", response_model=ScheduledExpenseOut, status_code=201)
def create_scheduled_expense(data: ScheduledExpenseIn, user: CurrentUser, db: DbSession):
    validate_refs(db, user.id, data.account_id, data.category_id)
    item = ScheduledExpense(user_id=user.id, **data.model_dump(), status="PLANNED")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/scheduled-expenses/{item_id}", response_model=ScheduledExpenseOut)
def patch_scheduled_expense(item_id: int, data: ScheduledExpensePatch, user: CurrentUser, db: DbSession):
    item = owned(db, ScheduledExpense, user.id, item_id)
    if item.status == "PAID":
        raise HTTPException(409, "Un gasto pagado queda vinculado a su movimiento")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("status") == "PAID":
        raise HTTPException(422, "Para marcar pagado, vincula un movimiento")
    if changes.get("status") is None and "status" in changes:
        raise HTTPException(422, "Estado obligatorio")
    update_model(db, item, data, ScheduledExpenseIn, user.id, category=True)
    db.commit()
    db.refresh(item)
    return item


@router.post("/scheduled-expenses/{item_id}/pay", response_model=ScheduledExpenseOut)
def pay_scheduled_expense(item_id: int, data: TransactionLinkIn, user: CurrentUser, db: DbSession):
    item = owned(db, ScheduledExpense, user.id, item_id)
    if item.status != "PLANNED":
        raise HTTPException(409, "El gasto no está pendiente")
    linked_transaction(db, user.id, data.transaction_id, "EXPENSE", item.account_id)
    item.transaction_id = data.transaction_id
    item.status = "PAID"
    db.commit()
    db.refresh(item)
    return item


@router.delete("/scheduled-expenses/{item_id}/pay", response_model=ScheduledExpenseOut)
def unpay_scheduled_expense(item_id: int, user: CurrentUser, db: DbSession):
    item = owned(db, ScheduledExpense, user.id, item_id)
    if item.status != "PAID":
        raise HTTPException(409, "El gasto no está marcado como pagado")
    item.status = "PLANNED"
    item.transaction_id = None
    db.commit()
    db.refresh(item)
    return item


@router.get("/debts", response_model=list[DebtOut])
def list_debts(user: CurrentUser, db: DbSession):
    return [debt_out(db, item) for item in db.scalars(select(Debt).where(Debt.user_id == user.id).order_by(Debt.id))]


@router.post("/debts", response_model=DebtOut, status_code=201)
def create_debt(data: DebtIn, user: CurrentUser, db: DbSession):
    validate_refs(db, user.id, data.account_id)
    item = Debt(user_id=user.id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return debt_out(db, item)


@router.patch("/debts/{item_id}", response_model=DebtOut)
def patch_debt(item_id: int, data: DebtPatch, user: CurrentUser, db: DbSession):
    item = owned(db, Debt, user.id, item_id)
    changes = data.model_dump(exclude_unset=True)
    if "account_id" in changes and changes["account_id"] != item.account_id and db.scalar(
        select(DebtPayment.id).where(DebtPayment.debt_id == item.id).limit(1)
    ):
        raise HTTPException(409, "No se puede cambiar la cuenta de una deuda con pagos")
    paid = item.principal - debt_remaining(db, item)
    if "principal" in changes and changes["principal"] is not None and changes["principal"] < paid:
        raise HTTPException(422, "El principal no puede ser inferior a lo ya pagado")
    update_model(db, item, data, DebtIn, user.id)
    db.commit()
    db.refresh(item)
    return debt_out(db, item)


@router.post("/debts/{item_id}/payments", response_model=DebtOut, status_code=201)
def pay_debt(item_id: int, data: TransactionLinkIn, user: CurrentUser, db: DbSession):
    item = owned(db, Debt, user.id, item_id)
    movement = linked_transaction(db, user.id, data.transaction_id, "EXPENSE", item.account_id)
    if movement.amount > debt_remaining(db, item):
        raise HTTPException(422, "El pago supera el principal pendiente")
    db.add(DebtPayment(user_id=user.id, debt_id=item.id, transaction_id=movement.id))
    db.commit()
    return debt_out(db, item)


@router.delete("/debts/{item_id}/payments/{link_id}", response_model=DebtOut)
def unpay_debt(item_id: int, link_id: int, user: CurrentUser, db: DbSession):
    item = owned(db, Debt, user.id, item_id)
    link = owned(db, DebtPayment, user.id, link_id)
    if link.debt_id != item_id:
        raise HTTPException(404, "Vínculo no encontrado")
    db.delete(link)
    db.commit()
    return debt_out(db, item)


@router.get("/upcoming", response_model=list[UpcomingEvent])
def upcoming(
    user: CurrentUser, db: DbSession, date_from: date | None = None,
    days: int = Query(90, ge=1, le=366),
):
    start = date_from or user_today(db, user.id)
    end = start + timedelta(days=days - 1)
    accounts = {item.id: item for item in db.scalars(select(Account).where(Account.user_id == user.id))}
    events: list[UpcomingEvent] = []

    def add(day: date, kind: str, item, amount: Decimal, overdue: bool = False):
        events.append(UpcomingEvent(
            date=day, kind=kind, source_id=item.id, name=item.name,
            amount=amount, account_id=item.account_id, currency=accounts[item.account_id].currency,
            overdue=overdue,
        ))

    for item in db.scalars(select(IncomeSource).where(IncomeSource.user_id == user.id, IncomeSource.active == True)):
        paid = set(db.scalars(select(IncomeReceipt.due_date).where(IncomeReceipt.source_id == item.id)))
        for day in income_dates(start, end, item.day_rule, item.day_of_month, item.starts_on, item.ends_on):
            if day not in paid:
                add(day, "INCOME", item, item.amount)
    for item in db.scalars(select(RecurringExpense).where(RecurringExpense.user_id == user.id, RecurringExpense.active == True)):
        paid = set(db.scalars(select(RecurringPayment.due_date).where(RecurringPayment.expense_id == item.id)))
        for day in recurring_dates(start, end, item.frequency, item.starts_on, item.ends_on):
            if day not in paid:
                add(day, "RECURRING", item, item.amount)
    for item in db.scalars(select(ScheduledExpense).where(
        ScheduledExpense.user_id == user.id, ScheduledExpense.status == "PLANNED", ScheduledExpense.due_date <= end
    )):
        add(item.due_date, "SCHEDULED", item, item.amount, item.due_date < start)
    for item in db.scalars(select(Debt).where(Debt.user_id == user.id, Debt.active == True)):
        remaining = debt_remaining(db, item)
        for day in monthly_dates(start, end, item.due_day, item.starts_on):
            if remaining <= 0:
                break
            amount = min(remaining, item.installment_amount)
            add(day, "DEBT", item, amount)
            remaining -= amount
    return sorted(events, key=lambda event: (event.date, event.kind, event.source_id))
