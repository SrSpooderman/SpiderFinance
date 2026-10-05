"""Pure rules for virtual reservations and savings proposals."""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def rule_amount(mode: str, value: Decimal, income: Decimal) -> Decimal:
    return (income * value / 100 if mode == "PERCENT" else value).quantize(CENT, rounding=ROUND_HALF_UP)


def recommendations(sources: list[dict], accounts: list[dict], rules: list[dict], goals: list[dict]) -> dict:
    by_source = {item["id"]: item for item in sources if item["active"]}
    by_account = {item["id"]: item for item in accounts}
    remaining_source = {item["id"]: item["amount"] for item in by_source.values()}
    available_by_currency: dict[str, Decimal] = {}
    suggestions = []
    for rule in sorted((item for item in rules if item["active"]), key=lambda item: item["id"]):
        source = by_source.get(rule["income_source_id"])
        if source is None or not by_account[source["account_id"]]["active"]:
            continue
        amount = min(rule_amount(rule["mode"], rule["value"], source["amount"]), remaining_source[source["id"]])
        remaining_source[source["id"]] -= amount
        currency = by_account[source["account_id"]]["currency"]
        available_by_currency[currency] = available_by_currency.get(currency, Decimal("0")) + amount
        suggestions.append({"rule_id": rule["id"], "source_id": source["id"], "currency": currency, "amount": amount})
    allocations = []
    for goal in sorted((item for item in goals if item["active"]), key=lambda item: (item["priority"], item["id"])):
        pending = max(Decimal("0"), goal["target_amount"] - goal["funded"])
        amount = min(pending, available_by_currency.get(goal["currency"], Decimal("0")))
        if amount:
            allocations.append({"goal_id": goal["id"], "currency": goal["currency"], "amount": amount})
            available_by_currency[goal["currency"]] -= amount
    return {"rules": suggestions, "allocations": allocations, "unallocated_by_currency": available_by_currency}
