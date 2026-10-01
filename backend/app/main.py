from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import accounts, auth, budgets, categories, dashboard, forecast, planning, savings, transactions
from app.core.config import settings
from app.core.db import engine

app = FastAPI(title="SpiderFinance API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",") if item.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

for router in (auth.router, accounts.router, categories.router, transactions.router, planning.router, forecast.router, savings.router, budgets.router, dashboard.router):
    app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}
