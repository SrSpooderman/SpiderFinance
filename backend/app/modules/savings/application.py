"""Savings use cases; no framework or SQLAlchemy dependency."""

from datetime import date
from decimal import Decimal

from app.modules.errors import UseCaseError
from app.modules.savings.domain import recommendations
from app.modules.savings.ports import SavingsStore


class Savings:
    def __init__(self, store: SavingsStore):
        self.store = store

    def _owned(self, kind: str, user_id: int, item_id: int) -> dict:
        item = getattr(self.store, kind)(user_id, item_id)
        if item is None:
            raise UseCaseError(404, "Elemento no encontrado")
        return item

    def _goal_out(self, item: dict) -> dict:
        return {**item, "funded": self.store.funded(item["id"])}

    def goals(self, user_id: int) -> list[dict]:
        return [self._goal_out(item) for item in self.store.goals(user_id)]

    def goal(self, user_id: int, goal_id: int) -> dict:
        return self._owned("goal", user_id, goal_id)

    def create_goal(self, user_id: int, values: dict) -> dict:
        return self._goal_out(self.store.add_goal(user_id, values))

    def update_goal(self, user_id: int, goal_id: int, values: dict, changes: dict) -> dict:
        item = self._owned("goal", user_id, goal_id)
        funded = self.store.funded(goal_id)
        if values["target_amount"] < funded:
            raise UseCaseError(422, "La meta no puede ser inferior al importe ya reservado")
        if values["currency"] != item["currency"] and funded > 0:
            raise UseCaseError(409, "Libera las reservas antes de cambiar la moneda")
        return self._goal_out(self.store.update_goal(user_id, goal_id, changes))

    def reservations(self, user_id: int) -> list[dict]:
        return self.store.reservations(user_id)

    def reserve(self, user_id: int, account_id: int, goal_id: int | None, amount: Decimal,
                day: date, notes: str | None) -> dict:
        account = self.store.account(user_id, account_id, lock=True)
        if account is None:
            raise UseCaseError(404, "Cuenta no encontrada")
        if not account["active"]:
            raise UseCaseError(422, "La cuenta está inactiva")
        if day > self.store.today(user_id):
            raise UseCaseError(422, "La reserva no puede registrarse en el futuro")
        goal = self._owned("goal", user_id, goal_id) if goal_id is not None else None
        if goal and (not goal["active"] or goal["currency"] != account["currency"]):
            raise UseCaseError(422, "El objetivo está inactivo o tiene otra moneda")
        if goal and self.store.funded(goal_id) + amount > goal["target_amount"]:
            raise UseCaseError(422, "La aportación supera la meta pendiente")
        free = self.store.account_balance(user_id, account_id) - self.store.reserved_on_account(account_id)
        if amount > free:
            raise UseCaseError(422, "No hay saldo disponible suficiente para reservar")
        existing = self.store.reservation_for(user_id, account_id, goal_id)
        current = existing["amount"] if existing else Decimal("0")
        item = self.store.set_reservation(user_id, account_id, goal_id, current + amount)
        if goal:
            self.store.add_contribution(user_id, goal_id, account_id, day, amount, notes)
        self.store.commit()
        return item

    def release(self, user_id: int, reservation_id: int, amount: Decimal, day: date, notes: str | None) -> dict:
        existing = self._owned("reservation", user_id, reservation_id)
        self.store.account(user_id, existing["account_id"], lock=True)
        item = self.store.reservation(user_id, reservation_id, lock=True)
        if item is None:
            raise UseCaseError(404, "Reserva no encontrada")
        if day > self.store.today(user_id):
            raise UseCaseError(422, "La liberación no puede registrarse en el futuro")
        if amount > item["amount"]:
            raise UseCaseError(422, "No puedes liberar más de lo reservado")
        result = self.store.set_reservation(user_id, item["account_id"], item["goal_id"], item["amount"] - amount)
        if item["goal_id"] is not None:
            self.store.add_contribution(user_id, item["goal_id"], item["account_id"], day, -amount, notes)
        self.store.commit()
        return result

    def contributions(self, user_id: int) -> list[dict]:
        return self.store.contributions(user_id)

    def rules(self, user_id: int) -> list[dict]:
        return self.store.rules(user_id)

    def rule(self, user_id: int, rule_id: int) -> dict:
        return self._owned("rule", user_id, rule_id)

    def _check_rule(self, mode: str, value: Decimal) -> None:
        if mode == "PERCENT" and value > 100:
            raise UseCaseError(422, "El porcentaje no puede superar el 100 %")

    def create_rule(self, user_id: int, values: dict) -> dict:
        self._owned("source", user_id, values["income_source_id"])
        self._check_rule(values["mode"], values["value"])
        return self.store.add_rule(user_id, values)

    def update_rule(self, user_id: int, rule_id: int, values: dict, changes: dict) -> dict:
        self._owned("rule", user_id, rule_id)
        self._owned("source", user_id, values["income_source_id"])
        self._check_rule(values["mode"], values["value"])
        return self.store.update_rule(user_id, rule_id, changes)

    def recommendations(self, user_id: int) -> dict:
        goals = self.goals(user_id)
        return recommendations(self.store.sources(user_id), self.store.accounts(user_id), self.store.rules(user_id), goals)
