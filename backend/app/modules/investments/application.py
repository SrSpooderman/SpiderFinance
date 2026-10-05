"""Investment use cases independent of HTTP and ORM."""

from app.modules.errors import UseCaseError
from app.modules.investments.domain import net_worth
from app.modules.investments.ports import InvestmentStore


class Investments:
    def __init__(self, store: InvestmentStore):
        self.store = store

    def position(self, user_id: int, position_id: int) -> dict:
        item = self.store.position(user_id, position_id)
        if item is None:
            raise UseCaseError(404, "Posición no encontrada")
        return item

    def investment_account(self, user_id: int, account_id: int) -> dict:
        account = self.store.account(user_id, account_id)
        if account is None:
            raise UseCaseError(404, "Cuenta no encontrada")
        if account["type"] != "INVESTMENT":
            raise UseCaseError(422, "La cuenta debe ser de tipo inversión")
        return account

    def validate_position(self, user_id: int, values: dict, exclude_id: int | None = None) -> None:
        self.investment_account(user_id, values["account_id"])
        if values["valued_on"] > self.store.today(user_id):
            raise UseCaseError(422, "La valoración no puede estar en el futuro")
        allocated = self.store.allocated_cost(user_id, values["account_id"], exclude_id)
        if allocated + values["cost_basis"] > self.store.balances(user_id)[values["account_id"]]:
            raise UseCaseError(422, "El coste de las posiciones supera el saldo aportado a la cuenta")

    def positions(self, user_id: int) -> list[dict]:
        return self.store.positions(user_id)

    def create_position(self, user_id: int, values: dict) -> dict:
        self.validate_position(user_id, values)
        return self.store.add_position(user_id, values)

    def update_position(self, user_id: int, position_id: int, values: dict, changes: dict) -> dict:
        self.position(user_id, position_id)
        self.validate_position(user_id, values, position_id)
        return self.store.update_position(user_id, position_id, changes)

    def delete_position(self, user_id: int, position_id: int) -> None:
        self.position(user_id, position_id)
        self.store.delete_position(user_id, position_id)

    def contributions(self, user_id: int) -> list[dict]:
        return self.store.contributions(user_id)

    def link_contribution(self, user_id: int, transaction_id: int) -> dict:
        movement = self.store.transaction(user_id, transaction_id)
        if movement is None:
            raise UseCaseError(404, "Movimiento no encontrado")
        if movement["type"] != "TRANSFER" or movement["status"] != "CLEARED" or movement["date"] > self.store.today(user_id):
            raise UseCaseError(422, "La aportación debe ser una transferencia confirmada y no futura")
        self.investment_account(user_id, movement["destination_account_id"])
        if self.store.contribution_for_transaction(transaction_id):
            raise UseCaseError(409, "La transferencia ya está vinculada")
        return self.store.add_contribution(user_id, movement["destination_account_id"], transaction_id)

    def unlink_contribution(self, user_id: int, contribution_id: int) -> None:
        if self.store.contribution(user_id, contribution_id) is None:
            raise UseCaseError(404, "Aportación no encontrada")
        self.store.delete_contribution(user_id, contribution_id)

    def net_worth(self, user_id: int) -> dict:
        return net_worth(self.store.today(user_id), self.store.accounts(user_id),
                         self.store.positions(user_id), self.store.balances(user_id), self.store.debts(user_id))

    def snapshots(self, user_id: int) -> list[dict]:
        return self.store.snapshots(user_id)

    def create_snapshot(self, user_id: int) -> list[dict]:
        report = self.net_worth(user_id)
        if self.store.snapshot_exists(user_id, report["date"]):
            raise UseCaseError(409, "Ya existe un snapshot para hoy")
        return self.store.add_snapshots(user_id, report["date"], report["currencies"])
