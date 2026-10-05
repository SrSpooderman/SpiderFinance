"""Pure parsing and spreadsheet sanitization rules."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

def string_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    return str(value).strip()


def parse_date(value: str) -> date:
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    raise ValueError(f"Fecha inválida: {value}")


def parse_amount(value: str) -> Decimal:
    raw = value.strip().replace(" ", "").replace("€", "").replace("$", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".") if len(raw.rsplit(",", 1)[1]) <= 2 else raw.replace(",", "")
    elif "." in raw and len(raw.rsplit(".", 1)[1]) == 3:
        raw = raw.replace(".", "")
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"Importe inválido: {value}") from None
    if not amount.is_finite() or amount == 0 or amount.as_tuple().exponent < -2:
        raise ValueError(f"Importe inválido: {value}")
    return amount


def parse_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in ("", "false", "0", "no"):
        return False
    if normalized in ("true", "1", "yes", "si", "sí"):
        return True
    raise ValueError(f"Valor booleano inválido: {value}")


def unescape_spreadsheet(value: str) -> str:
    return value[1:] if value.startswith(("'=", "'+", "'-", "'@")) else value


def parse_row(raw: dict, mapping: dict[str, str], default_account_id: int | None,
              positive_is_income: bool, spreadsheet_safe: bool = False) -> dict:
    def field(name: str) -> str:
        value = string_value(raw.get(mapping.get(name, ""), ""))
        return unescape_spreadsheet(value) if spreadsheet_safe else value

    day = parse_date(field("date"))
    amount = parse_amount(field("amount"))
    kind = field("type").upper()
    aliases = {"INGRESO": "INCOME", "GASTO": "EXPENSE", "TRANSFERENCIA": "TRANSFER",
               "INCOME": "INCOME", "EXPENSE": "EXPENSE", "TRANSFER": "TRANSFER"}
    if kind:
        kind = aliases.get(kind, kind)
    else:
        kind = "INCOME" if (amount > 0) == positive_is_income else "EXPENSE"
    concept = field("concept")
    if not concept:
        raise ValueError("Falta el concepto")
    source = field("source_account_id")
    destination = field("destination_account_id")
    account = field("account_id")
    selected = int(account) if account else default_account_id
    source_id = int(source) if source else (selected if kind == "EXPENSE" else None)
    destination_id = int(destination) if destination else (selected if kind == "INCOME" else None)
    category = field("category_id")
    status = field("status").upper() or "CLEARED"
    notes = field("notes")
    payment_method = field("payment_method")
    return {
        "date": day.isoformat(), "type": kind, "source_account_id": source_id,
        "destination_account_id": destination_id, "category_id": int(category) if category else None,
        "concept": concept, "amount": str(abs(amount)), "status": status,
        "notes": notes or None, "payment_method": payment_method or None,
        "is_fixed": parse_bool(field("is_fixed")), "is_necessary": parse_bool(field("is_necessary")),
    }
