from datetime import date

from fastapi import APIRouter, Query

from app.http.dependencies import CurrentUser, DbSession
from app.modules.forecasting.application import build_forecast
from app.modules.forecasting.infrastructure import SqlForecastReader
from app.modules.forecasting.schemas import ForecastOut, SalaryCycle
from app.modules.ledger.infrastructure import SqlLedgerStore
from app.modules.planning.application import salary_cycle as plan_salary_cycle
from app.modules.planning.infrastructure import SqlPlanningReader

router = APIRouter(tags=["forecast"])


def user_today(db: DbSession, user_id: int) -> date:
    return SqlLedgerStore(db).today(user_id)


def salary_cycle(db: DbSession, user_id: int, today: date) -> SalaryCycle:
    return SalaryCycle.model_validate(plan_salary_cycle(SqlPlanningReader(db), user_id, today))


@router.get("/salary-cycles", response_model=SalaryCycle)
def read_salary_cycle(user: CurrentUser, db: DbSession):
    return salary_cycle(db, user.id, user_today(db, user.id))


@router.get("/forecast", response_model=ForecastOut)
def read_forecast(user: CurrentUser, db: DbSession, days: int = Query(90, ge=1, le=366)):
    start = user_today(db, user.id)
    return ForecastOut.model_validate(build_forecast(
        SqlForecastReader(db, SqlLedgerStore(db)), SqlPlanningReader(db), user.id, start, days
    ))
