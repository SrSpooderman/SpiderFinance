from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.application.finance import account_balances
from app.infrastructure.models import Account, Category, Reservation, Transaction, UserSettings

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(user: CurrentUser, db: DbSession) -> dict:
    preferences = db.get(UserSettings, user.id)
    today = datetime.now(ZoneInfo(preferences.timezone)).date()
    all_accounts = db.scalars(select(Account).where(Account.user_id == user.id)).all()
    accounts = [account for account in all_accounts if account.active]
    account_by_id = {account.id: account for account in all_accounts}
    balances = account_balances(db, user.id, today)
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    savings: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    reserved: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for account in accounts:
        totals[account.currency] += balances[account.id]
        if account.type == "SAVINGS":
            savings[account.currency] += balances[account.id]
    active_accounts = {account.id: account for account in accounts}
    for reservation in db.scalars(select(Reservation).where(Reservation.user_id == user.id, Reservation.amount > 0)):
        account = active_accounts.get(reservation.account_id)
        if account is not None:
            reserved[account.currency] += reservation.amount
    categories = {category.id: category.name for category in db.scalars(select(Category).where(Category.user_id == user.id))}
    expenses = db.scalars(select(Transaction).where(
        Transaction.user_id == user.id,
        Transaction.type == "EXPENSE",
        Transaction.status == "CLEARED",
        Transaction.date >= today.replace(day=1),
        Transaction.date <= today,
    ))
    by_category: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    for movement in expenses:
        currency = account_by_id[movement.source_account_id].currency
        by_category[(currency, categories.get(movement.category_id, "Sin categoría"))] += movement.amount
    recent = db.scalars(select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.date.desc(), Transaction.id.desc()).limit(5)).all()
    return {
        "balances": [{
            "currency": currency, "total": str(total), "savings": str(savings[currency]),
            "reserved": str(reserved[currency]), "available": str(total - reserved[currency]),
        } for currency, total in sorted(totals.items())],
        "accounts": [{"id": account.id, "name": account.name, "type": account.type, "currency": account.currency, "balance": str(balances[account.id])} for account in accounts],
        "spending_by_category": [{"currency": currency, "name": name, "amount": str(amount)} for (currency, name), amount in sorted(by_category.items(), key=lambda x: x[1], reverse=True)],
        "recent_transactions": [{"id": item.id, "date": item.date.isoformat(), "type": item.type, "concept": item.concept, "amount": str(item.amount), "currency": account_by_id[item.source_account_id or item.destination_account_id].currency} for item in recent],
    }
