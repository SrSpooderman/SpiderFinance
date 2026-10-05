from fastapi import APIRouter

from app.http.dependencies import CurrentUser, DbSession
from app.modules.reporting.application import dashboard as build_dashboard
from app.modules.reporting.infrastructure import SqlDashboardReader
from app.modules.ledger.infrastructure import SqlLedgerStore

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(user: CurrentUser, db: DbSession) -> dict:
    return build_dashboard(SqlDashboardReader(db, SqlLedgerStore(db)), user.id)
