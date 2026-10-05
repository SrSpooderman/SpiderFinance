from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.db import engine
from app.modules.budgets import api as budgets
from app.modules.errors import UseCaseError
from app.modules.forecasting import api as forecast, scenarios_api as scenarios
from app.modules.identity import admin_api as admin, auth_api as auth
from app.modules.imports import api as imports
from app.modules.investments import api as investments
from app.modules.ledger import (
    accounts_api as accounts, categories_api as categories, transactions_api as transactions,
)
from app.modules.planning import api as planning
from app.modules.reporting import api as dashboard
from app.modules.savings import api as savings

app = FastAPI(title="SpiderFinance API", version="0.1.0")


@app.exception_handler(UseCaseError)
def use_case_error_handler(request, exc: UseCaseError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",") if item.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

for router in (auth.router, admin.router, accounts.router, categories.router, transactions.router, planning.router, forecast.router, savings.router, budgets.router, investments.router, imports.router, scenarios.router, dashboard.router):
    app.include_router(router, prefix="/api/v1")


@app.get("/api/", include_in_schema=False)
def api_root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}
