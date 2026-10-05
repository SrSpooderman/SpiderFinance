"""Dashboard composition over read ports."""

from collections import defaultdict
from decimal import Decimal

from app.modules.reporting.ports import DashboardReader


def dashboard(reader: DashboardReader, user_id: int) -> dict:
    today = reader.today(user_id)
    all_accounts = reader.accounts(user_id)
    accounts = [item for item in all_accounts if item["active"]]
    account_by_id = {item["id"]: item for item in all_accounts}
    balances = reader.balances(user_id, today)
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    savings: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    reserved: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for account in accounts:
        totals[account["currency"]] += balances[account["id"]]
        if account["type"] == "SAVINGS":
            savings[account["currency"]] += balances[account["id"]]
    active_accounts = {item["id"]: item for item in accounts}
    for item in reader.reservations(user_id):
        account = active_accounts.get(item["account_id"])
        if account is not None:
            reserved[account["currency"]] += item["amount"]
    categories = {item["id"]: item["name"] for item in reader.categories(user_id)}
    by_category: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    for movement in reader.expenses(user_id, today.replace(day=1), today):
        currency = account_by_id[movement["source_account_id"]]["currency"]
        by_category[(currency, categories.get(movement["category_id"], "Sin categoría"))] += movement["amount"]
    return {
        "balances": [{"currency": currency, "total": str(total), "savings": str(savings[currency]),
                      "reserved": str(reserved[currency]), "available": str(total - reserved[currency])}
                     for currency, total in sorted(totals.items())],
        "accounts": [{"id": item["id"], "name": item["name"], "type": item["type"],
                      "currency": item["currency"], "balance": str(balances[item["id"]])} for item in accounts],
        "spending_by_category": [{"currency": currency, "name": name, "amount": str(amount)}
                                 for (currency, name), amount in sorted(by_category.items(), key=lambda pair: pair[1], reverse=True)],
        "recent_transactions": [{"id": item["id"], "date": item["date"].isoformat(),
                                 "type": item["type"], "concept": item["concept"],
                                 "amount": str(item["amount"]),
                                 "currency": account_by_id[item["source_account_id"] or item["destination_account_id"]]["currency"]}
                                for item in reader.recent(user_id)],
    }
