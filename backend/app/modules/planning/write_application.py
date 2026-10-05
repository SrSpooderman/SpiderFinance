"""Planning commands and link invariants; depends on a persistence port."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.errors import UseCaseError
from app.modules.planning.domain import income_dates, recurring_dates
from app.modules.planning.write_ports import PlanningStore
from app.modules.savings.ports import SavingsRuleCleanup


class Planning:
    def __init__(self, store: PlanningStore, savings: SavingsRuleCleanup):
        self.store = store
        self.savings = savings

    def get(self, kind: str, user_id: int, item_id: int) -> dict:
        item = self.store.get(kind, user_id, item_id)
        if item is None:
            raise UseCaseError(404, "Elemento no encontrado")
        return item

    def list(self, kind: str, user_id: int) -> list[dict]:
        return self.store.list(kind, user_id)

    def _account(self, user_id: int, account_id: int, active: bool = False) -> dict:
        account = self.store.account(user_id, account_id)
        if account is None:
            raise UseCaseError(404, "Cuenta no encontrada")
        if active and not account["active"]:
            raise UseCaseError(422, "La cuenta está inactiva")
        return account

    def _refs(self, user_id: int, account_id: int, category_id: int | None = None) -> None:
        self._account(user_id, account_id, active=True)
        if category_id is not None and self.store.category(user_id, category_id) is None:
            raise UseCaseError(404, "Categoría no encontrada")

    def _update_refs(self, user_id: int, current: dict, values: dict, category: bool = False) -> None:
        self._account(user_id, values["account_id"], active=values["account_id"] != current["account_id"])
        if category and values["category_id"] is not None and self.store.category(user_id, values["category_id"]) is None:
            raise UseCaseError(404, "Categoría no encontrada")

    def _linked_transaction(self, user_id: int, transaction_id: int, kind: str, account_id: int) -> dict:
        movement = self.get("transaction", user_id, transaction_id)
        if movement["type"] != kind or movement["status"] != "CLEARED":
            raise UseCaseError(422, "El movimiento debe estar confirmado y tener el tipo correcto")
        if movement["date"] > self.store.today(user_id):
            raise UseCaseError(422, "Un movimiento futuro todavía no puede liquidar una obligación")
        if (movement["destination_account_id"] if kind == "INCOME" else movement["source_account_id"]) != account_id:
            raise UseCaseError(422, "La cuenta del movimiento no coincide con la planificación")
        if self.store.linked_any(transaction_id):
            raise UseCaseError(409, "El movimiento ya está vinculado a otra planificación")
        return movement

    def links(self, user_id: int) -> list[dict]:
        result = []
        for item in self.list("receipt", user_id):
            result.append({"id": item["id"], "kind": "INCOME", "source_id": item["source_id"],
                           "transaction_id": item["transaction_id"], "due_date": item["due_date"]})
        for item in self.list("recurring_payment", user_id):
            result.append({"id": item["id"], "kind": "RECURRING", "source_id": item["expense_id"],
                           "transaction_id": item["transaction_id"], "due_date": item["due_date"]})
        for item in self.list("scheduled", user_id):
            if item["status"] == "PAID":
                result.append({"id": item["id"], "kind": "SCHEDULED", "source_id": item["id"],
                               "transaction_id": item["transaction_id"], "due_date": item["due_date"]})
        for item in self.list("debt_payment", user_id):
            result.append({"id": item["id"], "kind": "DEBT", "source_id": item["debt_id"],
                           "transaction_id": item["transaction_id"]})
        return result

    def create_income(self, user_id: int, values: dict) -> dict:
        self._refs(user_id, values["account_id"])
        item = self.store.create("income", user_id, values, commit=False)
        if item["active"] and item["is_primary"]:
            self.store.clear_other_primary(user_id, item["id"])
        self.store.commit()
        return item

    def update_income(self, user_id: int, item_id: int, values: dict, changes: dict) -> dict:
        current = self.get("income", user_id, item_id)
        self._update_refs(user_id, current, values)
        item = self.store.update("income", user_id, item_id, changes, commit=False)
        if item["active"] and item["is_primary"]:
            self.store.clear_other_primary(user_id, item_id)
        self.store.commit()
        return item

    def delete_income(self, user_id: int, item_id: int) -> None:
        self.get("income", user_id, item_id)
        self.store.delete_related("receipt", user_id, "source_id", item_id)
        self.savings.delete_rules_for_source(user_id, item_id)
        self.store.delete("income", user_id, item_id)

    def link_income(self, user_id: int, item_id: int, due_date: date, transaction_id: int) -> dict:
        item = self.get("income", user_id, item_id)
        if due_date not in income_dates(due_date, due_date, item["day_rule"], item["day_of_month"],
                                        item["starts_on"], item["ends_on"]):
            raise UseCaseError(422, "La fecha no es un vencimiento de esta fuente")
        self._linked_transaction(user_id, transaction_id, "INCOME", item["account_id"])
        if self.store.exists("receipt", "source_id", item_id, {"due_date": due_date}):
            raise UseCaseError(409, "Este cobro ya está vinculado")
        link = self.store.create("receipt", user_id, {"source_id": item_id, "due_date": due_date,
                                                      "transaction_id": transaction_id})
        return {"id": link["id"]}

    def unlink_income(self, user_id: int, item_id: int, link_id: int) -> None:
        self.get("income", user_id, item_id)
        link = self.get("receipt", user_id, link_id)
        if link["source_id"] != item_id:
            raise UseCaseError(404, "Vínculo no encontrado")
        self.store.delete("receipt", user_id, link_id)

    def create_recurring(self, user_id: int, values: dict) -> dict:
        self._refs(user_id, values["account_id"], values["category_id"])
        return self.store.create("recurring", user_id, values)

    def update_recurring(self, user_id: int, item_id: int, values: dict, changes: dict) -> dict:
        current = self.get("recurring", user_id, item_id)
        self._update_refs(user_id, current, values, category=True)
        return self.store.update("recurring", user_id, item_id, changes)

    def delete_recurring(self, user_id: int, item_id: int) -> None:
        self.get("recurring", user_id, item_id)
        self.store.delete_related("recurring_payment", user_id, "expense_id", item_id)
        self.store.delete("recurring", user_id, item_id)

    def link_recurring(self, user_id: int, item_id: int, due_date: date, transaction_id: int) -> dict:
        item = self.get("recurring", user_id, item_id)
        if due_date not in recurring_dates(due_date, due_date, item["frequency"], item["starts_on"], item["ends_on"]):
            raise UseCaseError(422, "La fecha no es un vencimiento recurrente")
        self._linked_transaction(user_id, transaction_id, "EXPENSE", item["account_id"])
        if self.store.exists("recurring_payment", "expense_id", item_id, {"due_date": due_date}):
            raise UseCaseError(409, "Este vencimiento ya está vinculado")
        link = self.store.create("recurring_payment", user_id, {"expense_id": item_id, "due_date": due_date,
                                                                "transaction_id": transaction_id})
        return {"id": link["id"]}

    def unlink_recurring(self, user_id: int, item_id: int, link_id: int) -> None:
        self.get("recurring", user_id, item_id)
        link = self.get("recurring_payment", user_id, link_id)
        if link["expense_id"] != item_id:
            raise UseCaseError(404, "Vínculo no encontrado")
        self.store.delete("recurring_payment", user_id, link_id)

    def create_scheduled(self, user_id: int, values: dict) -> dict:
        self._refs(user_id, values["account_id"], values["category_id"])
        return self.store.create("scheduled", user_id, {**values, "status": "PLANNED"})

    def update_scheduled(self, user_id: int, item_id: int, values: dict, changes: dict) -> dict:
        current = self.get("scheduled", user_id, item_id)
        if current["status"] == "PAID":
            raise UseCaseError(409, "Un gasto pagado queda vinculado a su movimiento")
        if changes.get("status") == "PAID":
            raise UseCaseError(422, "Para marcar pagado, vincula un movimiento")
        if "status" in changes and changes["status"] is None:
            raise UseCaseError(422, "Estado obligatorio")
        self._update_refs(user_id, current, values, category=True)
        return self.store.update("scheduled", user_id, item_id, changes)

    def delete_scheduled(self, user_id: int, item_id: int) -> None:
        self.get("scheduled", user_id, item_id)
        self.store.delete("scheduled", user_id, item_id)

    def pay_scheduled(self, user_id: int, item_id: int, transaction_id: int) -> dict:
        item = self.get("scheduled", user_id, item_id)
        if item["status"] != "PLANNED":
            raise UseCaseError(409, "El gasto no está pendiente")
        self._linked_transaction(user_id, transaction_id, "EXPENSE", item["account_id"])
        return self.store.update("scheduled", user_id, item_id, {"transaction_id": transaction_id, "status": "PAID"})

    def unpay_scheduled(self, user_id: int, item_id: int) -> dict:
        item = self.get("scheduled", user_id, item_id)
        if item["status"] != "PAID":
            raise UseCaseError(409, "El gasto no está marcado como pagado")
        return self.store.update("scheduled", user_id, item_id, {"status": "PLANNED", "transaction_id": None})

    def debt_out(self, user_id: int, item: dict) -> dict:
        return {**item, "remaining": self.store.debt_remaining(user_id, item["id"], item["principal"])}

    def debts(self, user_id: int) -> list[dict]:
        return [self.debt_out(user_id, item) for item in self.list("debt", user_id)]

    def create_debt(self, user_id: int, values: dict) -> dict:
        self._refs(user_id, values["account_id"])
        return self.debt_out(user_id, self.store.create("debt", user_id, values))

    def update_debt(self, user_id: int, item_id: int, values: dict, changes: dict) -> dict:
        current = self.get("debt", user_id, item_id)
        if "account_id" in changes and changes["account_id"] != current["account_id"] and self.store.exists(
            "debt_payment", "debt_id", item_id
        ):
            raise UseCaseError(409, "No se puede cambiar la cuenta de una deuda con pagos")
        paid = current["principal"] - self.store.debt_remaining(user_id, item_id, current["principal"])
        if "principal" in changes and changes["principal"] is not None and changes["principal"] < paid:
            raise UseCaseError(422, "El principal no puede ser inferior a lo ya pagado")
        self._update_refs(user_id, current, values)
        return self.debt_out(user_id, self.store.update("debt", user_id, item_id, changes))

    def delete_debt(self, user_id: int, item_id: int) -> None:
        self.get("debt", user_id, item_id)
        self.store.delete_related("debt_payment", user_id, "debt_id", item_id)
        self.store.delete("debt", user_id, item_id)

    def pay_debt(self, user_id: int, item_id: int, transaction_id: int) -> dict:
        item = self.get("debt", user_id, item_id)
        movement = self._linked_transaction(user_id, transaction_id, "EXPENSE", item["account_id"])
        if movement["amount"] > self.store.debt_remaining(user_id, item_id, item["principal"]):
            raise UseCaseError(422, "El pago supera el principal pendiente")
        self.store.create("debt_payment", user_id, {"debt_id": item_id, "transaction_id": transaction_id})
        return self.debt_out(user_id, item)

    def unpay_debt(self, user_id: int, item_id: int, link_id: int) -> dict:
        item = self.get("debt", user_id, item_id)
        link = self.get("debt_payment", user_id, link_id)
        if link["debt_id"] != item_id:
            raise UseCaseError(404, "Vínculo no encontrado")
        self.store.delete("debt_payment", user_id, link_id)
        return self.debt_out(user_id, item)
