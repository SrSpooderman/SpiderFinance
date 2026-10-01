from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, DbSession
from app.api.savings_schemas import (
    ContributionIn, ContributionOut, GoalAllocation, GoalIn, GoalOut, GoalPatch,
    ReleaseIn, ReservationIn, ReservationOut, RuleSuggestion, SavingsRecommendation,
    SavingsRuleIn, SavingsRuleOut, SavingsRulePatch,
)
from app.application.finance import account_balance, user_today
from app.infrastructure.models import (
    Account, GoalContribution, IncomeSource, Reservation, SavingsGoal, SavingsRule,
)

router = APIRouter(tags=["savings"])
CENT = Decimal("0.01")


def owned(db: Session, model: type, user_id: int, item_id: int):
    item = db.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
    if item is None:
        raise HTTPException(404, "Elemento no encontrado")
    return item


def goal_funded(db: Session, goal_id: int) -> Decimal:
    return Decimal(db.scalar(select(func.coalesce(func.sum(Reservation.amount), 0)).where(Reservation.goal_id == goal_id)) or 0)


def goal_out(db: Session, item: SavingsGoal) -> GoalOut:
    return GoalOut(id=item.id, funded=goal_funded(db, item.id), **{key: getattr(item, key) for key in GoalIn.model_fields})


def reserved_on_account(db: Session, account_id: int) -> Decimal:
    return Decimal(db.scalar(select(func.coalesce(func.sum(Reservation.amount), 0)).where(Reservation.account_id == account_id)) or 0)


def check_rule(mode: str, value: Decimal) -> None:
    if mode == "PERCENT" and value > 100:
        raise HTTPException(422, "El porcentaje no puede superar el 100 %")


@router.get("/goals", response_model=list[GoalOut])
def list_goals(user: CurrentUser, db: DbSession):
    return [goal_out(db, item) for item in db.scalars(
        select(SavingsGoal).where(SavingsGoal.user_id == user.id).order_by(SavingsGoal.priority, SavingsGoal.id)
    )]


@router.post("/goals", response_model=GoalOut, status_code=201)
def create_goal(data: GoalIn, user: CurrentUser, db: DbSession):
    item = SavingsGoal(user_id=user.id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return goal_out(db, item)


@router.patch("/goals/{item_id}", response_model=GoalOut)
def patch_goal(item_id: int, data: GoalPatch, user: CurrentUser, db: DbSession):
    item = owned(db, SavingsGoal, user.id, item_id)
    changes = data.model_dump(exclude_unset=True)
    values = {key: getattr(item, key) for key in GoalIn.model_fields}
    values.update(changes)
    try:
        GoalIn.model_validate(values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    funded = goal_funded(db, item.id)
    if values["target_amount"] < funded:
        raise HTTPException(422, "La meta no puede ser inferior al importe ya reservado")
    if values["currency"] != item.currency and funded > 0:
        raise HTTPException(409, "Libera las reservas antes de cambiar la moneda")
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return goal_out(db, item)


@router.get("/reservations", response_model=list[ReservationOut])
def list_reservations(user: CurrentUser, db: DbSession):
    return db.scalars(select(Reservation).where(
        Reservation.user_id == user.id, Reservation.amount > 0
    ).order_by(Reservation.id)).all()


def reserve(db: Session, user_id: int, account_id: int, goal_id: int | None, amount: Decimal, day, notes):
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user_id).with_for_update())
    if account is None:
        raise HTTPException(404, "Cuenta no encontrada")
    if not account.active:
        raise HTTPException(422, "La cuenta está inactiva")
    if day > user_today(db, user_id):
        raise HTTPException(422, "La reserva no puede registrarse en el futuro")
    goal = owned(db, SavingsGoal, user_id, goal_id) if goal_id is not None else None
    if goal and (not goal.active or goal.currency != account.currency):
        raise HTTPException(422, "El objetivo está inactivo o tiene otra moneda")
    if goal and goal_funded(db, goal.id) + amount > goal.target_amount:
        raise HTTPException(422, "La aportación supera la meta pendiente")
    free = account_balance(db, user_id, account_id) - reserved_on_account(db, account_id)
    if amount > free:
        raise HTTPException(422, "No hay saldo disponible suficiente para reservar")
    reservation = db.scalar(select(Reservation).where(
        Reservation.user_id == user_id, Reservation.account_id == account_id, Reservation.goal_id == goal_id
    ))
    if reservation is None:
        reservation = Reservation(user_id=user_id, account_id=account_id, goal_id=goal_id, amount=Decimal("0"))
        db.add(reservation)
        db.flush()
    reservation.amount += amount
    if goal:
        db.add(GoalContribution(user_id=user_id, goal_id=goal.id, account_id=account_id, date=day, amount=amount, notes=notes))
    db.commit()
    db.refresh(reservation)
    return reservation


@router.post("/reservations", response_model=ReservationOut, status_code=201)
def create_reservation(data: ReservationIn, user: CurrentUser, db: DbSession):
    return reserve(db, user.id, data.account_id, data.goal_id, data.amount, data.date, data.notes)


@router.post("/goals/{item_id}/contributions", response_model=ReservationOut, status_code=201)
def contribute_to_goal(item_id: int, data: ContributionIn, user: CurrentUser, db: DbSession):
    owned(db, SavingsGoal, user.id, item_id)
    return reserve(db, user.id, data.account_id, item_id, data.amount, data.date, data.notes)


@router.post("/reservations/{item_id}/release", response_model=ReservationOut)
def release_reservation(item_id: int, data: ReleaseIn, user: CurrentUser, db: DbSession):
    existing = owned(db, Reservation, user.id, item_id)
    db.scalar(select(Account).where(Account.id == existing.account_id).with_for_update())
    item = db.scalar(select(Reservation).where(
        Reservation.id == item_id, Reservation.user_id == user.id
    ).with_for_update().execution_options(populate_existing=True))
    if item is None:
        raise HTTPException(404, "Reserva no encontrada")
    if data.date > user_today(db, user.id):
        raise HTTPException(422, "La liberación no puede registrarse en el futuro")
    if data.amount > item.amount:
        raise HTTPException(422, "No puedes liberar más de lo reservado")
    item.amount -= data.amount
    if item.goal_id is not None:
        db.add(GoalContribution(
            user_id=user.id, goal_id=item.goal_id, account_id=item.account_id,
            date=data.date, amount=-data.amount, notes=data.notes,
        ))
    db.commit()
    db.refresh(item)
    return item


@router.get("/goal-contributions", response_model=list[ContributionOut])
def list_contributions(user: CurrentUser, db: DbSession):
    return db.scalars(select(GoalContribution).where(
        GoalContribution.user_id == user.id
    ).order_by(GoalContribution.date.desc(), GoalContribution.id.desc())).all()


@router.get("/savings-rules", response_model=list[SavingsRuleOut])
def list_rules(user: CurrentUser, db: DbSession):
    return db.scalars(select(SavingsRule).where(SavingsRule.user_id == user.id).order_by(SavingsRule.id)).all()


@router.post("/savings-rules", response_model=SavingsRuleOut, status_code=201)
def create_rule(data: SavingsRuleIn, user: CurrentUser, db: DbSession):
    owned(db, IncomeSource, user.id, data.income_source_id)
    check_rule(data.mode, data.value)
    item = SavingsRule(user_id=user.id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/savings-rules/{item_id}", response_model=SavingsRuleOut)
def patch_rule(item_id: int, data: SavingsRulePatch, user: CurrentUser, db: DbSession):
    item = owned(db, SavingsRule, user.id, item_id)
    changes = data.model_dump(exclude_unset=True)
    values = {key: getattr(item, key) for key in SavingsRuleIn.model_fields}
    values.update(changes)
    try:
        validated = SavingsRuleIn.model_validate(values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    owned(db, IncomeSource, user.id, validated.income_source_id)
    check_rule(validated.mode, validated.value)
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.get("/savings-recommendations", response_model=SavingsRecommendation)
def savings_recommendations(user: CurrentUser, db: DbSession):
    sources = {item.id: item for item in db.scalars(select(IncomeSource).where(
        IncomeSource.user_id == user.id, IncomeSource.active == True
    ))}
    accounts = {item.id: item for item in db.scalars(select(Account).where(Account.user_id == user.id))}
    remaining_source = {item.id: item.amount for item in sources.values()}
    proposed_by_currency: dict[str, Decimal] = {}
    suggestions = []
    for rule in db.scalars(select(SavingsRule).where(
        SavingsRule.user_id == user.id, SavingsRule.active == True
    ).order_by(SavingsRule.id)):
        source = sources.get(rule.income_source_id)
        if source is None or not accounts[source.account_id].active:
            continue
        desired = (source.amount * rule.value / 100 if rule.mode == "PERCENT" else rule.value).quantize(CENT, rounding=ROUND_HALF_UP)
        amount = min(desired, remaining_source[source.id])
        remaining_source[source.id] -= amount
        currency = accounts[source.account_id].currency
        proposed_by_currency[currency] = proposed_by_currency.get(currency, Decimal("0")) + amount
        suggestions.append(RuleSuggestion(rule_id=rule.id, source_id=source.id, currency=currency, amount=amount))
    allocations = []
    for goal in db.scalars(select(SavingsGoal).where(
        SavingsGoal.user_id == user.id, SavingsGoal.active == True
    ).order_by(SavingsGoal.priority, SavingsGoal.id)):
        pending = max(Decimal("0"), goal.target_amount - goal_funded(db, goal.id))
        available = proposed_by_currency.get(goal.currency, Decimal("0"))
        amount = min(pending, available)
        if amount:
            allocations.append(GoalAllocation(goal_id=goal.id, currency=goal.currency, amount=amount))
            proposed_by_currency[goal.currency] -= amount
    return SavingsRecommendation(rules=suggestions, allocations=allocations, unallocated_by_currency=proposed_by_currency)
