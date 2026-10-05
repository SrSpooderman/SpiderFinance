"""Pure accounting rules. Amounts are Decimal and balances are derived."""

from datetime import date
from decimal import Decimal

from app.modules.ledger.types import TransactionType


class LedgerRuleError(ValueError):
    pass


def validate_movement_shape(values: dict) -> None:
    kind = values["type"]
    source = values.get("source_account_id")
    destination = values.get("destination_account_id")
    if kind == TransactionType.INCOME and (source is not None or destination is None):
        raise LedgerRuleError("Un ingreso requiere solo una cuenta destino")
    if kind == TransactionType.EXPENSE and (source is None or destination is not None):
        raise LedgerRuleError("Un gasto requiere solo una cuenta origen")
    if kind == TransactionType.TRANSFER and (source is None or destination is None or source == destination):
        raise LedgerRuleError("Una transferencia requiere dos cuentas distintas")
    if kind == TransactionType.ADJUSTMENT and ((source is None) == (destination is None)):
        raise LedgerRuleError("Un ajuste requiere exactamente una cuenta")


def validate_transfer_currency(source: dict | None, destination: dict | None) -> None:
    if source and destination and source["currency"] != destination["currency"]:
        raise LedgerRuleError("La transferencia entre monedas distintas requiere conversión")


def movement_effects(values: dict | None, today: date) -> dict[int, Decimal]:
    if values is None or values["status"] != "CLEARED" or values["date"] > today:
        return {}
    result: dict[int, Decimal] = {}
    if values.get("source_account_id") is not None:
        account_id = values["source_account_id"]
        result[account_id] = result.get(account_id, Decimal("0")) - values["amount"]
    if values.get("destination_account_id") is not None:
        account_id = values["destination_account_id"]
        result[account_id] = result.get(account_id, Decimal("0")) + values["amount"]
    return result


def balances(accounts: list[dict], movements: list[dict]) -> dict[int, Decimal]:
    result = {account["id"]: account["initial_balance"] for account in accounts}
    for movement in movements:
        if movement["source_account_id"] is not None:
            result[movement["source_account_id"]] -= movement["amount"]
        if movement["destination_account_id"] is not None:
            result[movement["destination_account_id"]] += movement["amount"]
    return result


def reconciliation_movement(user_id: int, account_id: int, day: date, difference: Decimal, notes: str | None) -> dict:
    return {
        "user_id": user_id, "date": day, "type": TransactionType.ADJUSTMENT,
        "source_account_id": account_id if difference < 0 else None,
        "destination_account_id": account_id if difference > 0 else None,
        "concept": "Ajuste de conciliación", "amount": abs(difference),
        "notes": notes, "status": "CLEARED", "reconciliation": True,
    }
