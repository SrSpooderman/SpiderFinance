"""Scenario simulation over an already built forecast."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

from app.modules.errors import UseCaseError
from app.modules.forecasting.domain import CashEvent, project


def validate_extra_accounts(data: dict, owned_active_ids: set[int]) -> None:
    account_ids = {item["account_id"] for item in data["events"]}
    if not account_ids.issubset(owned_active_ids):
        raise UseCaseError(422, "Los sucesos adicionales deben usar cuentas activas propias")


class ScenarioStore(Protocol):
    def active_account_ids(self, user_id: int) -> set[int]: ...
    def list(self, user_id: int) -> list[dict]: ...
    def get(self, user_id: int, scenario_id: int) -> dict | None: ...
    def create(self, user_id: int, values: dict) -> dict: ...
    def update(self, user_id: int, scenario_id: int, values: dict) -> dict: ...
    def delete(self, user_id: int, scenario_id: int) -> None: ...


class Scenarios:
    def __init__(self, store: ScenarioStore):
        self.store = store

    def validate(self, user_id: int, data: dict) -> None:
        validate_extra_accounts(data, self.store.active_account_ids(user_id))

    def _out(self, item: dict) -> dict:
        return {"id": item["id"], "name": item["name"], "notes": item["notes"], **item["changes"]}

    def list(self, user_id: int) -> list[dict]:
        return [self._out(item) for item in self.store.list(user_id)]

    def get(self, user_id: int, scenario_id: int) -> dict:
        item = self.store.get(user_id, scenario_id)
        if item is None:
            raise UseCaseError(404, "Escenario no encontrado")
        return self._out(item)

    def create(self, user_id: int, data: dict, changes: dict) -> dict:
        self.validate(user_id, data)
        item = self.store.create(user_id, {"name": data["name"], "notes": data["notes"], "changes": changes})
        return self._out(item)

    def update(self, user_id: int, scenario_id: int, data: dict, changes: dict) -> dict:
        self.get(user_id, scenario_id)
        self.validate(user_id, data)
        item = self.store.update(user_id, scenario_id, {"name": data["name"], "notes": data["notes"], "changes": changes})
        return self._out(item)

    def delete(self, user_id: int, scenario_id: int) -> None:
        self.get(user_id, scenario_id)
        self.store.delete(user_id, scenario_id)


def simulate(data: dict, baseline: dict) -> dict:
    accounts = {item["id"]: item for item in baseline["accounts"]}
    initial = {item["id"]: item["current"] for item in baseline["accounts"]}
    changes = {item["key"]: item["amount"] for item in data["overrides"]}
    matched = {event["key"] for event in baseline["events"] if event["key"] in changes}
    events = [CashEvent(event["date"], event["account_id"], changes.get(event["key"], event["amount"]),
                        event["key"], event["label"]) for event in baseline["events"]]
    ignored_events = 0
    for index, event in enumerate(data["events"]):
        if event["account_id"] not in initial or event["date"] < baseline["start"] or event["date"] > baseline["end"]:
            ignored_events += 1
            continue
        events.append(CashEvent(event["date"], event["account_id"], event["amount"],
                                f"scenario:{index}", event["label"]))
    timeline = project(initial, events, baseline["start"], baseline["end"])
    comparison = []
    minimum: dict[str, Decimal] = {}
    minimum_available: dict[str, Decimal] = {}
    simulated_savings: dict[str, Decimal] = {}
    savings_events: list[tuple[date, str, Decimal]] = []
    if data["savings_percent"] is not None:
        for event in events:
            if event.key.startswith("plan:INCOME:") and event.amount > 0:
                currency = accounts[event.account_id]["currency"]
                saved = (event.amount * data["savings_percent"] / Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                savings_events.append((event.date, currency, saved))
    savings_events.sort(key=lambda item: item[0])
    savings_index = 0
    for base_day, simulated in zip(baseline["days"], timeline, strict=True):
        while savings_index < len(savings_events) and savings_events[savings_index][0] <= simulated.date:
            _, currency, saved = savings_events[savings_index]
            simulated_savings[currency] = simulated_savings.get(currency, Decimal("0")) + saved
            savings_index += 1
        totals: dict[str, Decimal] = {}
        for account_id, amount in simulated.balances.items():
            currency = accounts[account_id]["currency"]
            totals[currency] = totals.get(currency, Decimal("0")) + amount
        difference = {currency: totals.get(currency, Decimal("0")) - base_day["totals_by_currency"].get(currency, Decimal("0"))
                      for currency in set(totals) | set(base_day["totals_by_currency"])}
        base_available = {currency: amount - baseline["reserved_by_currency"].get(currency, Decimal("0"))
                          for currency, amount in base_day["totals_by_currency"].items()}
        scenario_available = {currency: amount - baseline["reserved_by_currency"].get(currency, Decimal("0"))
                              - simulated_savings.get(currency, Decimal("0")) for currency, amount in totals.items()}
        for currency, amount in totals.items():
            minimum[currency] = min(minimum.get(currency, amount), amount)
            available = scenario_available[currency]
            minimum_available[currency] = min(minimum_available.get(currency, available), available)
        comparison.append({"date": simulated.date, "baseline_by_currency": base_day["totals_by_currency"],
                           "scenario_by_currency": totals, "difference_by_currency": difference,
                           "baseline_available_by_currency": base_available,
                           "scenario_available_by_currency": scenario_available})
    return {
        "name": data["name"], "start": baseline["start"], "end": baseline["end"], "baseline": baseline,
        "days": comparison, "final_difference_by_currency": comparison[-1]["difference_by_currency"],
        "minimum_scenario_by_currency": minimum,
        "minimum_scenario_available_by_currency": minimum_available,
        "simulated_savings_by_currency": simulated_savings,
        "ignored_overrides": sorted(set(changes) - matched), "ignored_events": ignored_events,
    }
