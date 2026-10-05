"""Forecast query composed from planning and ledger read ports."""

from datetime import date, timedelta
from decimal import Decimal

from app.modules.forecasting.domain import CashEvent, project
from app.modules.forecasting.ports import ForecastReader
from app.modules.planning.application import salary_cycle, upcoming
from app.modules.planning.ports import PlanningReader


def build_forecast(reader: ForecastReader, planner: PlanningReader, user_id: int, start: date, days: int) -> dict:
    end = start + timedelta(days=days - 1)
    accounts = reader.active_accounts(user_id)
    currencies = {account["id"]: account["currency"] for account in accounts}
    balances = reader.balances(user_id, start)
    initial = {account["id"]: balances[account["id"]] for account in accounts}
    reserved: dict[str, Decimal] = {}
    for item in reader.reservations(user_id):
        if item["account_id"] in initial:
            currency = currencies[item["account_id"]]
            reserved[currency] = reserved.get(currency, Decimal("0")) + item["amount"]
    events: list[CashEvent] = []
    for item in upcoming(planner, user_id, start, days):
        if item["account_id"] in initial:
            events.append(CashEvent(
                date=max(item["date"], start), account_id=item["account_id"],
                amount=item["amount"] if item["kind"] == "INCOME" else -item["amount"],
                key=f"plan:{item['kind']}:{item['source_id']}:{item['date']}", label=item["name"],
            ))
    for item in reader.pending_movements(user_id, start, end):
        when = max(item["date"], start)
        if item["source_account_id"] in initial:
            events.append(CashEvent(when, item["source_account_id"], -item["amount"],
                                    f"transaction:{item['id']}:out", item["concept"]))
        if item["destination_account_id"] in initial:
            events.append(CashEvent(when, item["destination_account_id"], item["amount"],
                                    f"transaction:{item['id']}:in", item["concept"]))
    timeline = project(initial, events, start, end)

    def totals(day) -> dict[str, Decimal]:
        result: dict[str, Decimal] = {}
        for account_id, value in day.balances.items():
            currency = currencies[account_id]
            result[currency] = result.get(currency, Decimal("0")) + value
        return result

    cycle = salary_cycle(planner, user_id, start)
    available_now: dict[str, Decimal] = {}
    for account_id, value in initial.items():
        currency = currencies[account_id]
        available_now[currency] = available_now.get(currency, Decimal("0")) + value
    available_now = {currency: value - reserved.get(currency, Decimal("0"))
                     for currency, value in available_now.items()}
    until = [day for day in timeline if cycle["next_payday"] is not None and day.date < cycle["next_payday"]] if cycle["available"] else []
    minimum = None
    if until:
        minimum = {}
        for day in until:
            for currency, value in totals(day).items():
                available = value - reserved.get(currency, Decimal("0"))
                minimum[currency] = min(minimum.get(currency, available), available)
    return {
        "start": start, "end": end, "salary_cycle": cycle,
        "accounts": [{"id": account["id"], "name": account["name"], "currency": account["currency"],
                      "current": initial[account["id"]], "projected": timeline[-1].balances[account["id"]]}
                     for account in accounts],
        "events": [{"date": event.date, "account_id": event.account_id, "amount": event.amount,
                    "label": event.label, "key": event.key}
                   for event in sorted(events, key=lambda event: (event.date, event.key))],
        "days": [{"date": day.date, "balances": day.balances, "totals_by_currency": totals(day)} for day in timeline],
        "reserved_by_currency": reserved, "available_now_by_currency": available_now,
        "minimum_until_payday_by_currency": minimum,
    }
