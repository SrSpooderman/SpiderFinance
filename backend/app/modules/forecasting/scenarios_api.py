"""Saved and one-off what-if simulations over the cash-flow forecast."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, model_validator

from app.http.dependencies import CurrentUser, DbSession
from app.modules.forecasting import api as forecast_http
from app.modules.forecasting.application import build_forecast
from app.modules.forecasting.infrastructure import SqlForecastReader
from app.modules.forecasting.schemas import ForecastOut
from app.modules.ledger.infrastructure import SqlLedgerStore
from app.modules.planning.infrastructure import SqlPlanningReader
from app.modules.forecasting.scenario_application import Scenarios, simulate as simulate_scenario
from app.modules.forecasting.scenario_infrastructure import SqlScenarioStore

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


def scenarios(db: DbSession) -> Scenarios:
    return Scenarios(SqlScenarioStore(db))


def simulate(data: ScenarioIn, user: CurrentUser, db: DbSession, days: int) -> SimulationOut:
    start = forecast_http.user_today(db, user.id)
    baseline = build_forecast(SqlForecastReader(db, SqlLedgerStore(db)), SqlPlanningReader(db), user.id, start, days)
    result = simulate_scenario(data.model_dump(), baseline)
    return SimulationOut.model_validate(result)


@router.get("/scenarios", response_model=list[ScenarioOut])
def list_scenarios(user: CurrentUser, db: DbSession):
    return scenarios(db).list(user.id)


@router.post("/scenarios", response_model=ScenarioOut, status_code=201)
def create_scenario(data: ScenarioIn, user: CurrentUser, db: DbSession):
    changes = data.model_dump(mode="json", exclude={"name", "notes"})
    return scenarios(db).create(user.id, data.model_dump(), changes)


@router.post("/scenarios/simulate", response_model=SimulationOut)
def preview_scenario(data: ScenarioIn, user: CurrentUser, db: DbSession,
                     days: int = Query(90, ge=1, le=366)):
    scenarios(db).validate(user.id, data.model_dump())
    return simulate(data, user, db, days)


@router.get("/scenarios/{item_id}", response_model=ScenarioOut)
def read_scenario(item_id: int, user: CurrentUser, db: DbSession):
    return scenarios(db).get(user.id, item_id)


@router.patch("/scenarios/{item_id}", response_model=ScenarioOut)
def patch_scenario(item_id: int, data: ScenarioIn, user: CurrentUser, db: DbSession):
    changes = data.model_dump(mode="json", exclude={"name", "notes"})
    return scenarios(db).update(user.id, item_id, data.model_dump(), changes)


@router.delete("/scenarios/{item_id}", status_code=204)
def delete_scenario(item_id: int, user: CurrentUser, db: DbSession):
    scenarios(db).delete(user.id, item_id)


@router.get("/scenarios/{item_id}/compare", response_model=SimulationOut)
def compare_scenario(item_id: int, user: CurrentUser, db: DbSession,
                     days: int = Query(90, ge=1, le=366)):
    return simulate(ScenarioIn.model_validate(scenarios(db).get(user.id, item_id)), user, db, days)
