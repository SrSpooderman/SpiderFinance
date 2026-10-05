"""Ledger use cases. This layer depends only on the ledger port and pure rules."""

from datetime import date
from decimal import Decimal

from app.modules.ledger.domain import (
    LedgerRuleError, balances, movement_effects, reconciliation_movement,
    validate_movement_shape, validate_transfer_currency,
)
from app.modules.ledger.ports import LedgerPolicies, LedgerStore
from app.modules.errors import UseCaseError


class LedgerError(UseCaseError):
    pass


class Ledger:
    def __init__(self, store: LedgerStore, policies: LedgerPolicies):
        self.store = store
        self.policies = policies

    def account(self, user_id: int, account_id: int) -> dict:
        item = self.store.account(user_id, account_id)
        if item is None:
            raise LedgerError(404, "Cuenta no encontrada")
        return item

    def category(self, user_id: int, category_id: int) -> dict:
        item = self.store.category(user_id, category_id)
        if item is None:
            raise LedgerError(404, "Categoría no encontrada")
        return item

    def transaction(self, user_id: int, transaction_id: int) -> dict:
        item = self.store.transaction(user_id, transaction_id)
        if item is None:
            raise LedgerError(404, "Movimiento no encontrado")
        return item

    def balances(self, user_id: int, as_of: date | None = None) -> dict[int, Decimal]:
        return balances(self.store.accounts(user_id), self.store.cleared_movements(
            user_id, as_of or self.store.today(user_id)
        ))

    def balance(self, user_id: int, account_id: int, as_of: date | None = None) -> Decimal:
        self.account(user_id, account_id)
        return self.balances(user_id, as_of)[account_id]

    def list_accounts(self, user_id: int) -> list[dict]:
        amounts = self.balances(user_id)
        return [{**item, "balance": amounts[item["id"]]} for item in self.store.accounts(user_id)]

    def read_account(self, user_id: int, account_id: int) -> dict:
        item = self.account(user_id, account_id)
        return {**item, "balance": self.balance(user_id, account_id)}

    def create_account(self, user_id: int, values: dict) -> dict:
        item = self.store.add_account(user_id, values)
        return {**item, "balance": item["initial_balance"]}

    def update_account(self, user_id: int, account_id: int, changes: dict) -> dict:
        current = self.account(user_id, account_id)
        if any(changes[key] is None for key in ("name", "type", "initial_balance", "currency", "active") if key in changes):
            raise LedgerError(422, "Campo obligatorio nulo")
        positions, contributions, movements = self.policies.account_references(user_id, account_id)
        if positions and any(key in changes and changes[key] != current[key]
                             for key in ("type", "currency", "initial_balance")):
            raise LedgerError(409, "La cuenta tiene posiciones de inversión; corrígelas antes de cambiar tipo, moneda o saldo inicial")
        if contributions and "type" in changes and changes["type"] != current["type"]:
            raise LedgerError(409, "La cuenta tiene aportaciones de inversión vinculadas")
        if movements and ("initial_balance" in changes or "currency" in changes):
            raise LedgerError(409, "Con movimientos existentes, usa conciliación y no cambies el saldo inicial ni la moneda")
        item = self.store.update_account(user_id, account_id, changes)
        return {**item, "balance": self.balance(user_id, account_id)}

    def reconcile(self, user_id: int, account_id: int, day: date, observed: Decimal, notes: str | None) -> dict:
        self.account(user_id, account_id)
        difference = observed - self.balance(user_id, account_id, day)
        if difference == 0:
            return {"difference": Decimal("0.00"), "transaction": None}
        values = reconciliation_movement(user_id, account_id, day, difference, notes)
        return {"difference": difference, "transaction": self.store.add_transaction(user_id, values)}

    def validate_category(self, user_id: int, name: str, parent_id: int | None, exclude_id: int | None = None) -> None:
        if parent_id is not None:
            parent = self.category(user_id, parent_id)
            if parent["parent_id"] is not None:
                raise LedgerError(422, "Solo se admite un nivel de subcategorías")
            if parent_id == exclude_id:
                raise LedgerError(422, "Una categoría no puede ser su propio padre")
        if self.store.sibling_category(user_id, name, parent_id, exclude_id):
            raise LedgerError(409, "Ya existe una categoría con ese nombre en este nivel")

    def list_categories(self, user_id: int) -> list[dict]:
        return self.store.categories(user_id)

    def create_category(self, user_id: int, values: dict) -> dict:
        self.validate_category(user_id, values["name"], values.get("parent_id"))
        return self.store.add_category(user_id, values)

    def update_category(self, user_id: int, category_id: int, changes: dict) -> dict:
        current = self.category(user_id, category_id)
        if "name" in changes and changes["name"] is None:
            raise LedgerError(422, "El nombre no puede ser nulo")
        parent_id = changes.get("parent_id", current["parent_id"])
        if parent_id is not None and self.store.has_child_categories(category_id):
            raise LedgerError(422, "Una categoría con subcategorías no puede convertirse en subcategoría")
        self.validate_category(user_id, changes.get("name", current["name"]), parent_id, category_id)
        return self.store.update_category(user_id, category_id, changes)

    def delete_category(self, user_id: int, category_id: int) -> None:
        self.category(user_id, category_id)
        if self.policies.category_references(category_id) or self.store.has_child_categories(category_id):
            raise LedgerError(409, "La categoría está en uso")
        self.store.delete_category(user_id, category_id)

    def validate_transaction(self, user_id: int, values: dict) -> None:
        try:
            validate_movement_shape(values)
            source = self.account(user_id, values["source_account_id"]) if values.get("source_account_id") is not None else None
            destination = self.account(user_id, values["destination_account_id"]) if values.get("destination_account_id") is not None else None
            validate_transfer_currency(source, destination)
        except LedgerRuleError as exc:
            raise LedgerError(422, str(exc)) from exc
        if values.get("category_id") is not None:
            self.category(user_id, values["category_id"])

    def ensure_unlinked(self, transaction_id: int) -> None:
        if self.policies.linked_transaction(transaction_id):
            raise LedgerError(409, "El movimiento está vinculado a una operación registrada y no se puede modificar")

    def ensure_investment_capacity(self, user_id: int, old: dict | None, new: dict | None) -> None:
        today = self.store.today(user_id)
        before = movement_effects(old, today)
        after = movement_effects(new, today)
        amounts = self.balances(user_id)
        for account_id in before.keys() | after.keys():
            cost = self.policies.investment_cost(user_id, account_id)
            if cost and amounts[account_id] + after.get(account_id, Decimal("0")) - before.get(account_id, Decimal("0")) < cost:
                raise LedgerError(409, "El movimiento dejaría una cuenta de inversión sin saldo para sus posiciones")

    def list_transactions(self, user_id: int, filters: dict, page: int, page_size: int) -> dict:
        items, total = self.store.transactions(user_id, filters, page, page_size)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def create_transaction(self, user_id: int, values: dict) -> dict:
        self.validate_transaction(user_id, values)
        self.ensure_investment_capacity(user_id, None, values)
        return self.store.add_transaction(user_id, values)

    def update_transaction(self, user_id: int, transaction_id: int, changes: dict, fields: tuple[str, ...]) -> dict:
        current = self.transaction(user_id, transaction_id)
        self.ensure_unlinked(transaction_id)
        if any(changes[key] is None for key in ("date", "type", "concept", "amount", "is_fixed", "is_necessary", "status") if key in changes):
            raise LedgerError(422, "Campo obligatorio nulo")
        values = {key: current[key] for key in fields}
        values.update(changes)
        self.validate_transaction(user_id, values)
        self.ensure_investment_capacity(user_id, current, values)
        return self.store.update_transaction(user_id, transaction_id, changes)

    def delete_transaction(self, user_id: int, transaction_id: int) -> None:
        current = self.transaction(user_id, transaction_id)
        self.ensure_unlinked(transaction_id)
        self.ensure_investment_capacity(user_id, current, None)
        self.store.delete_transaction(user_id, transaction_id)
