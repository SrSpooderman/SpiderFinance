"""Budget use cases and reports independent of persistence and HTTP."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from app.modules.budgets.ports import BudgetStore
from app.modules.errors import UseCaseError
from app.modules.planning.application import salary_cycle
from app.modules.planning.ports import PlanningReader


class Budgets:
    def __init__(self, store: BudgetStore, planner: PlanningReader):
        self.store = store
        self.planner = planner

    def window(self, user_id: int, period: str, as_of: date) -> tuple[date, date] | None:
        if period == "MONTH":
            return as_of.replace(day=1), as_of.replace(day=monthrange(as_of.year, as_of.month)[1])
        cycle = salary_cycle(self.planner, user_id, as_of)
        if cycle.get("current_start") is None or cycle.get("current_end") is None:
            return None
        return cycle["current_start"], cycle["current_end"]

    def _category(self, user_id: int, category_id: int | None) -> None:
        if category_id is not None and self.store.category(user_id, category_id) is None:
            raise UseCaseError(404, "Categoría no encontrada")

    def _unique(self, user_id: int, values: dict, exclude_id: int | None = None) -> None:
        for item in self.store.budgets(user_id):
            if item["id"] != exclude_id and all(item[key] == values[key] for key in ("period", "category_id", "currency")):
                raise UseCaseError(409, "Ya existe un presupuesto para esa categoría, moneda y periodo")

    def list(self, user_id: int) -> list[dict]:
        return self.store.budgets(user_id)

    def get(self, user_id: int, budget_id: int) -> dict:
        item = self.store.budget(user_id, budget_id)
        if item is None:
            raise UseCaseError(404, "Presupuesto no encontrado")
        return item

    def create(self, user_id: int, values: dict) -> dict:
        self._category(user_id, values["category_id"])
        self._unique(user_id, values)
        return self.store.add_budget(user_id, values)

    def update(self, user_id: int, budget_id: int, values: dict, changes: dict) -> dict:
        self.get(user_id, budget_id)
        self._category(user_id, values["category_id"])
        self._unique(user_id, values, budget_id)
        return self.store.update_budget(user_id, budget_id, changes)

    def status(self, user_id: int, as_of: date | None = None) -> list[dict]:
        reference = as_of or self.store.today(user_id)
        accounts = {item["id"]: item for item in self.store.accounts(user_id)}
        categories = self.store.categories(user_id)
        children = {item["id"]: {item["id"], *(child["id"] for child in categories if child["parent_id"] == item["id"])}
                    for item in categories}
        results = []
        for item in self.store.budgets(user_id):
            period = self.window(user_id, item["period"], reference)
            spent = None
            if period:
                spent = sum((movement["amount"] for movement in self.store.actuals(user_id, *period)
                             if movement["type"] == "EXPENSE"
                             and accounts[movement["source_account_id"]]["currency"] == item["currency"]
                             and (item["category_id"] is None or movement["category_id"] in children.get(
                                 item["category_id"], {item["category_id"]}))), Decimal("0"))
            results.append({**item, "start": period[0] if period else None, "end": period[1] if period else None,
                            "spent": spent, "remaining": item["amount"] - spent if spent is not None else None})
        return results

    def statistics(self, user_id: int, period: str, as_of: date | None = None) -> dict:
        dates = self.window(user_id, period, as_of or self.store.today(user_id))
        if dates is None:
            raise UseCaseError(422, "Configura una fuente de ingreso principal para usar ciclos de nómina")
        start, end = dates
        accounts = {item["id"]: item for item in self.store.accounts(user_id)}
        categories = {item["id"]: item for item in self.store.categories(user_id)}
        income: dict[str, Decimal] = {}
        expense: dict[str, Decimal] = {}
        category_totals: dict[tuple[int | None, str], Decimal] = {}
        daily: dict[tuple[date, str], Decimal] = {}
        for movement in self.store.actuals(user_id, start, end):
            account_id = movement["destination_account_id"] if movement["type"] == "INCOME" else movement["source_account_id"]
            currency = accounts[account_id]["currency"]
            if movement["type"] == "INCOME":
                income[currency] = income.get(currency, Decimal("0")) + movement["amount"]
                continue
            expense[currency] = expense.get(currency, Decimal("0")) + movement["amount"]
            key = movement["category_id"], currency
            category_totals[key] = category_totals.get(key, Decimal("0")) + movement["amount"]
            daily_key = movement["date"], currency
            daily[daily_key] = daily.get(daily_key, Decimal("0")) + movement["amount"]
        by_category = []
        for (category_id, currency), amount in category_totals.items():
            category = categories.get(category_id)
            parent = categories.get(category["parent_id"]) if category and category["parent_id"] else None
            name = f"{parent['name']} / {category['name']}" if parent else category["name"] if category else "Sin categoría"
            by_category.append({"category_id": category_id, "name": name, "currency": currency, "amount": amount})
        return {"period": period, "start": start, "end": end,
                "income_by_currency": income, "expense_by_currency": expense,
                "expenses_by_category": sorted(by_category, key=lambda item: (item["currency"], -item["amount"], item["name"])),
                "daily_expenses": [{"date": day, "currency": currency, "amount": amount}
                                   for (day, currency), amount in sorted(daily.items())]}
