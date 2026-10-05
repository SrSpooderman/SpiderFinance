"""Portfolio valuation by currency without exchange-rate assumptions."""

from datetime import date
from decimal import Decimal


def net_worth(day: date, accounts: list[dict], positions: list[dict],
              balances: dict[int, Decimal], debts: list[dict]) -> dict:
    by_account: dict[int, list[dict]] = {}
    for position in positions:
        by_account.setdefault(position["account_id"], []).append(position)
    totals: dict[str, dict[str, Decimal]] = {}
    accounts_out = []
    for account in accounts:
        balance = balances[account["id"]]
        holdings = by_account.get(account["id"], [])
        cost = sum((item["cost_basis"] for item in holdings), Decimal("0"))
        position_value = sum((item["market_value"] for item in holdings), Decimal("0"))
        uninvested = balance - cost if account["type"] == "INVESTMENT" else balance
        value = uninvested + position_value if account["type"] == "INVESTMENT" else balance
        accounts_out.append({
            "id": account["id"], "name": account["name"], "type": account["type"],
            "currency": account["currency"], "book_balance": balance,
            "position_value": position_value, "uninvested_cash": uninvested, "asset_value": value,
        })
        currency = totals.setdefault(account["currency"], {"assets": Decimal("0"), "liabilities": Decimal("0")})
        if value >= 0:
            currency["assets"] += value
        else:
            currency["liabilities"] -= value
    by_id = {account["id"]: account for account in accounts}
    for debt in debts:
        currency = by_id[debt["account_id"]]["currency"]
        totals.setdefault(currency, {"assets": Decimal("0"), "liabilities": Decimal("0")})["liabilities"] += debt["remaining"]
    return {
        "date": day,
        "currencies": [{"currency": currency, "assets": values["assets"],
                        "liabilities": values["liabilities"],
                        "net_worth": values["assets"] - values["liabilities"]}
                       for currency, values in sorted(totals.items())],
        "accounts": accounts_out,
    }
