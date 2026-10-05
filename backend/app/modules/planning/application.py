"""Planning queries shared by the HTTP adapter and forecasting."""

from datetime import date, timedelta
from decimal import Decimal

from app.modules.planning.domain import income_dates, monthly_dates, recurring_dates
from app.modules.planning.ports import PlanningReader


def salary_cycle(reader: PlanningReader, user_id: int, today: date) -> dict:
    source = next((item for item in reader.income_sources(user_id) if item["is_primary"]), None)
    if source is None:
        return {"available": False}
    dates = income_dates(today - timedelta(days=80), today + timedelta(days=80),
                         source["day_rule"], source["day_of_month"], source["starts_on"], source["ends_on"])
    previous = max((day for day in dates if day <= today), default=None)
    next_payday = min((day for day in dates if day > today), default=None)
    return {
        "available": previous is not None and next_payday is not None,
        "source_id": source["id"],
        "current_start": previous if previous and next_payday else None,
        "current_end": next_payday - timedelta(days=1) if previous and next_payday else None,
        "next_payday": next_payday,
    }


def upcoming(reader: PlanningReader, user_id: int, start: date, days: int) -> list[dict]:
    end = start + timedelta(days=days - 1)
    accounts = {item["id"]: item for item in reader.accounts(user_id)}
    events: list[dict] = []

    def add(day: date, kind: str, item: dict, amount: Decimal, overdue: bool = False) -> None:
        events.append({
            "date": day, "kind": kind, "source_id": item["id"], "name": item["name"],
            "amount": amount, "account_id": item["account_id"],
            "currency": accounts[item["account_id"]]["currency"], "overdue": overdue,
        })

    for item in reader.income_sources(user_id):
        paid = reader.income_receipt_dates(item["id"])
        for day in income_dates(start, end, item["day_rule"], item["day_of_month"], item["starts_on"], item["ends_on"]):
            if day not in paid:
                add(day, "INCOME", item, item["amount"])
    for item in reader.recurring_expenses(user_id):
        paid = reader.recurring_payment_dates(item["id"])
        for day in recurring_dates(start.replace(day=1), end, item["frequency"], item["starts_on"], item["ends_on"]):
            if day not in paid:
                add(day, "RECURRING", item, item["amount"], day < start)
    for item in reader.scheduled_expenses(user_id, end):
        add(item["due_date"], "SCHEDULED", item, item["amount"], item["due_date"] < start)
    for item in reader.debts(user_id):
        remaining = reader.debt_remaining(user_id, item["id"], item["principal"])
        for day in monthly_dates(start, end, item["due_day"], item["starts_on"]):
            if remaining <= 0:
                break
            amount = min(remaining, item["installment_amount"])
            add(day, "DEBT", item, amount)
            remaining -= amount
    return sorted(events, key=lambda event: (event["date"], event["kind"], event["source_id"]))
