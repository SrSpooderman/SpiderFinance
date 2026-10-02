"""Saved and one-off what-if simulations over the cash-flow forecast."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.api.forecast import ForecastOut, read_forecast
from app.application.forecast import CashEvent, project
from app.infrastructure.models import Account, Scenario

router = APIRouter(tags=["scenarios"])


class EventOverride(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(max_digits=18, decimal_places=2)


class ExtraEvent(BaseModel):
    date: date
    account_id: int
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    label: str = Field(min_length=1, max_length=120)


class ScenarioIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=500)
    overrides: list[EventOverride] = Field(default_factory=list, max_length=100)
    events: list[ExtraEvent] = Field(default_factory=list, max_length=100)
    savings_percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)

    @model_validator(mode="after")
    def unique_overrides(self):
        keys = [item.key for item in self.overrides]
        if len(keys) != len(set(keys)):
            raise ValueError("Un suceso solo puede modificarse una vez")
        return self


class ScenarioOut(ScenarioIn):
    id: int


class ComparisonDay(BaseModel):
    date: date
    baseline_by_currency: dict[str, Decimal]
    scenario_by_currency: dict[str, Decimal]
    difference_by_currency: dict[str, Decimal]
    baseline_available_by_currency: dict[str, Decimal]
    scenario_available_by_currency: dict[str, Decimal]


class SimulationOut(BaseModel):
    name: str
    start: date
    end: date
    baseline: ForecastOut
    days: list[ComparisonDay]
    final_difference_by_currency: dict[str, Decimal]
    minimum_scenario_by_currency: dict[str, Decimal]
    minimum_scenario_available_by_currency: dict[str, Decimal]
    simulated_savings_by_currency: dict[str, Decimal]
    ignored_overrides: list[str]
    ignored_events: int


def checked_changes(data: ScenarioIn, db: DbSession, user_id: int) -> dict:
    account_ids = {item.account_id for item in data.events}
    owned = set(db.scalars(select(Account.id).where(
        Account.user_id == user_id, Account.active == True, Account.id.in_(account_ids)
    ))) if account_ids else set()
    if account_ids != owned:
        raise HTTPException(422, "Los sucesos adicionales deben usar cuentas activas propias")
    return data.model_dump(mode="json", exclude={"name", "notes"})


def scenario_out(item: Scenario) -> ScenarioOut:
    return ScenarioOut(id=item.id, name=item.name, notes=item.notes, **item.changes)


def get_scenario(db: DbSession, user_id: int, item_id: int) -> Scenario:
    item = db.scalar(select(Scenario).where(Scenario.id == item_id, Scenario.user_id == user_id))
    if item is None:
        raise HTTPException(404, "Escenario no encontrado")
    return item


def simulate(data: ScenarioIn, user: CurrentUser, db: DbSession, days: int) -> SimulationOut:
    baseline = read_forecast(user, db, days)
    accounts = {item.id: item for item in baseline.accounts}
    initial = {item.id: item.current for item in baseline.accounts}
    changes = {item.key: item.amount for item in data.overrides}
    matched = {event.key for event in baseline.events if event.key in changes}
    events = [CashEvent(
        event.date, event.account_id, changes.get(event.key, event.amount), event.key, event.label
    ) for event in baseline.events]
    ignored_events = 0
    for index, event in enumerate(data.events):
        if event.account_id not in initial or event.date < baseline.start or event.date > baseline.end:
            ignored_events += 1
            continue
        events.append(CashEvent(event.date, event.account_id, event.amount,
                                f"scenario:{index}", event.label))
    timeline = project(initial, events, baseline.start, baseline.end)
    comparison: list[ComparisonDay] = []
    minimum: dict[str, Decimal] = {}
    minimum_available: dict[str, Decimal] = {}
    simulated_savings: dict[str, Decimal] = {}
    savings_events: list[tuple[date, str, Decimal]] = []
    if data.savings_percent is not None:
        for event in events:
            if event.key.startswith("plan:INCOME:") and event.amount > 0:
                currency = accounts[event.account_id].currency
                saved = (event.amount * data.savings_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                savings_events.append((event.date, currency, saved))
    savings_events.sort(key=lambda item: item[0])
    savings_index = 0
    for base_day, simulated in zip(baseline.days, timeline, strict=True):
        while savings_index < len(savings_events) and savings_events[savings_index][0] <= simulated.date:
            _, currency, saved = savings_events[savings_index]
            simulated_savings[currency] = simulated_savings.get(currency, Decimal("0")) + saved
            savings_index += 1
        totals: dict[str, Decimal] = {}
        for account_id, amount in simulated.balances.items():
            currency = accounts[account_id].currency
            totals[currency] = totals.get(currency, Decimal("0")) + amount
        difference = {currency: totals.get(currency, Decimal("0")) - base_day.totals_by_currency.get(currency, Decimal("0"))
                      for currency in set(totals) | set(base_day.totals_by_currency)}
        base_available = {currency: amount - baseline.reserved_by_currency.get(currency, Decimal("0"))
                          for currency, amount in base_day.totals_by_currency.items()}
        scenario_available = {currency: amount - baseline.reserved_by_currency.get(currency, Decimal("0"))
                              - simulated_savings.get(currency, Decimal("0")) for currency, amount in totals.items()}
        for currency, amount in totals.items():
            minimum[currency] = min(minimum.get(currency, amount), amount)
            available = scenario_available[currency]
            minimum_available[currency] = min(minimum_available.get(currency, available), available)
        comparison.append(ComparisonDay(date=simulated.date, baseline_by_currency=base_day.totals_by_currency,
                                        scenario_by_currency=totals, difference_by_currency=difference,
                                        baseline_available_by_currency=base_available,
                                        scenario_available_by_currency=scenario_available))
    return SimulationOut(
        name=data.name, start=baseline.start, end=baseline.end, baseline=baseline,
        days=comparison, final_difference_by_currency=comparison[-1].difference_by_currency,
        minimum_scenario_by_currency=minimum,
        minimum_scenario_available_by_currency=minimum_available,
        simulated_savings_by_currency=simulated_savings,
        ignored_overrides=sorted(set(changes) - matched), ignored_events=ignored_events,
    )


@router.get("/scenarios", response_model=list[ScenarioOut])
def list_scenarios(user: CurrentUser, db: DbSession):
    return [scenario_out(item) for item in db.scalars(select(Scenario).where(
        Scenario.user_id == user.id).order_by(Scenario.id.desc()))]


@router.post("/scenarios", response_model=ScenarioOut, status_code=201)
def create_scenario(data: ScenarioIn, user: CurrentUser, db: DbSession):
    changes = checked_changes(data, db, user.id)
    item = Scenario(user_id=user.id, name=data.name, notes=data.notes, changes=changes)
    db.add(item)
    db.commit()
    db.refresh(item)
    return scenario_out(item)


@router.post("/scenarios/simulate", response_model=SimulationOut)
def preview_scenario(data: ScenarioIn, user: CurrentUser, db: DbSession,
                     days: int = Query(90, ge=1, le=366)):
    checked_changes(data, db, user.id)
    return simulate(data, user, db, days)


@router.get("/scenarios/{item_id}", response_model=ScenarioOut)
def read_scenario(item_id: int, user: CurrentUser, db: DbSession):
    return scenario_out(get_scenario(db, user.id, item_id))


@router.patch("/scenarios/{item_id}", response_model=ScenarioOut)
def patch_scenario(item_id: int, data: ScenarioIn, user: CurrentUser, db: DbSession):
    item = get_scenario(db, user.id, item_id)
    item.name = data.name
    item.notes = data.notes
    item.changes = checked_changes(data, db, user.id)
    db.commit()
    db.refresh(item)
    return scenario_out(item)


@router.delete("/scenarios/{item_id}", status_code=204)
def delete_scenario(item_id: int, user: CurrentUser, db: DbSession):
    db.delete(get_scenario(db, user.id, item_id))
    db.commit()


@router.get("/scenarios/{item_id}/compare", response_model=SimulationOut)
def compare_scenario(item_id: int, user: CurrentUser, db: DbSession,
                     days: int = Query(90, ge=1, le=366)):
    return simulate(scenario_out(get_scenario(db, user.id, item_id)), user, db, days)
