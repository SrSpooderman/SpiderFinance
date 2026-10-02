"""Import the supplied personal-finance workbook into an empty user account.

The workbook is an input file, never part of the application image or repository.
Summary/formula sheets are deliberately ignored: they are derived or hypothetical.
"""

import argparse
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.calendar import income_day, month_day
from app.application.finance import account_balances
from app.application.importing import parse_amount, parse_date, parse_file
from app.core.db import SessionLocal
from app.infrastructure.models import (
    Account, Budget, Category, GoalContribution, IncomeReceipt, IncomeSource,
    RecurringExpense, RecurringPayment, Reservation, SavingsGoal, SavingsRule,
    ScheduledExpense, Transaction, User,
)

REQUIRED_HEADERS = {
    "Cuentas": {"Cuenta", "Tipo", "Banco/Entidad", "Saldo inicial", "Saldo actual", "Activa"},
    "Configuración": {"Categorías"},
    "Movimientos": {"Fecha", "Cuenta origen", "Cuenta destino", "Tipo", "Categoría", "Subcategoría", "Concepto", "Importe", "Fijo", "Necesario", "Método de pago", "Notas"},
    "Presupuesto": {"Categoría", "Presupuesto mensual"},
    "Gastos fijos": {"Concepto", "Categoría", "Importe", "Periodicidad", "Día aproximado", "Cuenta", "Activo", "Inicio", "Fin"},
    "Ingresos fijos": {"Concepto", "Importe", "Periodicidad", "Cuenta destino", "Activo", "Notas"},
    "Objetivos": {"Objetivo", "Objetivo €", "Ahorrado", "Fecha objetivo"},
}


@dataclass(frozen=True)
class TemplateData:
    accounts: list[dict]
    categories: list[str]
    movements: list[dict]
    budgets: list[dict]
    fixed_expenses: list[dict]
    incomes: list[dict]
    goals: list[dict]
    savings_percent: Decimal | None
    last_movement: date
    savings_account_name: str | None

    def counts(self) -> str:
        return (
            f"{len(self.accounts)} cuentas, {len(self.categories)} categorías principales, "
            f"{len(self.movements)} movimientos, {len(self.budgets)} presupuestos, "
            f"{len(self.fixed_expenses)} gastos planificados, {len(self.incomes)} fuentes de ingreso "
            f"y {len(self.goals)} objetivos"
        )


def money(raw: str, label: str, *, zero: bool = False) -> Decimal:
    value = raw.strip()
    if zero and value.replace(",", ".") in {"0", "0.0", "0.00"}:
        return Decimal("0.00")
    try:
        result = parse_amount(value)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc
    if not zero and result <= 0:
        raise ValueError(f"{label}: el importe debe ser positivo")
    return result


def yes_no(raw: str, label: str) -> bool:
    normalized = unicodedata.normalize("NFKD", raw.strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    if normalized in {"si", "yes", "true", "1"}:
        return True
    if normalized in {"no", "false", "0"}:
        return False
    raise ValueError(f"{label}: indica Sí o No")


def maybe_date(raw: str) -> date | None:
    return parse_date(raw) if raw else None


def unique_names(items: list[dict], field: str, sheet: str) -> None:
    names = [item[field] for item in items]
    if len(names) != len(set(names)):
        raise ValueError(f"{sheet}: hay nombres duplicados")


def read_template(path: Path) -> TemplateData:
    contents = path.read_bytes()
    sheets = parse_file(contents, path.name)
    for name, required in REQUIRED_HEADERS.items():
        if name not in sheets:
            raise ValueError(f"Falta la hoja {name}")
        if missing := required - set(sheets[name][0]):
            raise ValueError(f"{name}: faltan columnas {', '.join(sorted(missing))}")

    def rows(name: str, key: str):
        return [(number, row) for number, row in sheets[name][1] if row.get(key, "").strip()]

    accounts = []
    type_map = {"Corriente": "CHECKING", "Ahorro": "SAVINGS", "Efectivo": "CASH", "Inversión": "INVESTMENT", "Tarjeta": "CARD", "Otro": "OTHER"}
    for number, row in rows("Cuentas", "Cuenta"):
        if row["Tipo"] not in type_map:
            raise ValueError(f"Cuentas fila {number}: tipo desconocido")
        accounts.append({
            "name": row["Cuenta"], "type": type_map[row["Tipo"]],
            "institution": row["Banco/Entidad"] or None,
            "initial_balance": money(row["Saldo inicial"], f"Cuentas fila {number}", zero=True),
            "expected_balance": money(row["Saldo actual"], f"Cuentas fila {number}", zero=True),
            "active": yes_no(row["Activa"], f"Cuentas fila {number}"),
            "notes": row.get("Notas") or None,
        })
    unique_names(accounts, "name", "Cuentas")
    if not accounts:
        raise ValueError("Cuentas: no hay cuentas")
    account_names = {item["name"] for item in accounts}
    categories = [row["Categorías"] for _, row in rows("Configuración", "Categorías")]
    if not categories or len(categories) != len(set(categories)):
        raise ValueError("Configuración: categorías ausentes o duplicadas")
    category_names = set(categories)

    movements = []
    kinds = {"Ingreso": "INCOME", "Gasto": "EXPENSE", "Transferencia": "TRANSFER"}
    for number, row in rows("Movimientos", "Fecha"):
        kind = kinds.get(row["Tipo"])
        if kind is None:
            raise ValueError(f"Movimientos fila {number}: tipo desconocido")
        source = row["Cuenta origen"] or None
        destination = row["Cuenta destino"] or None
        if any(name not in account_names for name in (source, destination) if name):
            raise ValueError(f"Movimientos fila {number}: cuenta desconocida")
        if (kind == "INCOME" and (source or not destination)) or (kind == "EXPENSE" and (not source or destination)) or (kind == "TRANSFER" and (not source or not destination or source == destination)):
            raise ValueError(f"Movimientos fila {number}: cuentas incompatibles con el tipo")
        category = row["Categoría"] or None
        if category and category not in category_names:
            raise ValueError(f"Movimientos fila {number}: categoría desconocida")
        subcategory = row["Subcategoría"] or None
        if subcategory and not category:
            raise ValueError(f"Movimientos fila {number}: subcategoría sin categoría")
        reconciliation = subcategory == "Conciliación" and row["Concepto"].lower().startswith("ajuste de conciliación")
        movements.append({
            "row_number": number, "raw": row, "date": parse_date(row["Fecha"]),
            "type": "ADJUSTMENT" if reconciliation else kind,
            "source": source, "destination": destination,
            "category": category, "subcategory": subcategory,
            "concept": row["Concepto"], "amount": money(row["Importe"], f"Movimientos fila {number}"),
            "is_fixed": yes_no(row["Fijo"], f"Movimientos fila {number}, Fijo"),
            "is_necessary": yes_no(row["Necesario"], f"Movimientos fila {number}, Necesario"),
            "payment_method": row["Método de pago"] or None,
            "notes": row["Notas"] or None, "reconciliation": reconciliation,
        })
    if not movements:
        raise ValueError("Movimientos: no hay datos")
    last_movement = max(item["date"] for item in movements)

    balances = {item["name"]: item["initial_balance"] for item in accounts}
    for movement in movements:
        if movement["source"]:
            balances[movement["source"]] -= movement["amount"]
        if movement["destination"]:
            balances[movement["destination"]] += movement["amount"]
    for account in accounts:
        if balances[account["name"]] != account["expected_balance"]:
            raise ValueError(f"Cuentas: el saldo calculado de {account['name']} no coincide con el Excel")

    budgets = []
    for number, row in rows("Presupuesto", "Categoría"):
        if row["Categoría"] not in category_names:
            raise ValueError(f"Presupuesto fila {number}: categoría desconocida")
        budgets.append({"category": row["Categoría"], "amount": money(row["Presupuesto mensual"], f"Presupuesto fila {number}")})
    unique_names(budgets, "category", "Presupuesto")

    fixed_expenses = []
    for number, row in rows("Gastos fijos", "Concepto"):
        if row["Cuenta"] not in account_names or row["Categoría"] not in category_names:
            raise ValueError(f"Gastos fijos fila {number}: cuenta o categoría desconocida")
        frequency = row["Periodicidad"]
        if frequency not in {"Mensual", "Único"}:
            raise ValueError(f"Gastos fijos fila {number}: periodicidad desconocida")
        day_value = Decimal(row["Día aproximado"])
        due_day = int(day_value)
        if day_value != due_day or not 1 <= due_day <= 31:
            raise ValueError(f"Gastos fijos fila {number}: día inválido")
        start = maybe_date(row["Inicio"])
        end = maybe_date(row["Fin"])
        if frequency == "Único" and start is None:
            raise ValueError(f"Gastos fijos fila {number}: falta la fecha del gasto único")
        if start and end and end < start:
            raise ValueError(f"Gastos fijos fila {number}: la fecha final precede al inicio")
        fixed_expenses.append({
            "name": row["Concepto"], "category": row["Categoría"],
            "amount": money(row["Importe"], f"Gastos fijos fila {number}"),
            "frequency": frequency, "due_day": due_day, "account": row["Cuenta"],
            "active": yes_no(row["Activo"], f"Gastos fijos fila {number}"),
            "start": start, "end": end,
        })
    unique_names(fixed_expenses, "name", "Gastos fijos")

    incomes = []
    for number, row in rows("Ingresos fijos", "Concepto"):
        if row["Cuenta destino"] not in account_names:
            raise ValueError(f"Ingresos fijos fila {number}: cuenta desconocida")
        if row["Periodicidad"] != "Mensual":
            raise ValueError(f"Ingresos fijos fila {number}: periodicidad desconocida")
        notes = unicodedata.normalize("NFKD", row["Notas"].lower())
        notes = "".join(char for char in notes if not unicodedata.combining(char))
        if "ultimo dia" not in notes:
            raise ValueError(f"Ingresos fijos fila {number}: falta la regla de cobro (último día)")
        incomes.append({
            "name": row["Concepto"], "amount": money(row["Importe"], f"Ingresos fijos fila {number}"),
            "account": row["Cuenta destino"], "active": yes_no(row["Activo"], f"Ingresos fijos fila {number}"),
        })
    unique_names(incomes, "name", "Ingresos fijos")

    goals = []
    for number, row in rows("Objetivos", "Objetivo"):
        target = money(row["Objetivo €"], f"Objetivos fila {number}")
        funded = money(row["Ahorrado"], f"Objetivos fila {number}", zero=True)
        if funded < 0 or funded > target:
            raise ValueError(f"Objetivos fila {number}: ahorro fuera de la meta")
        goals.append({"name": row["Objetivo"], "target": target, "funded": funded,
                      "due_date": maybe_date(row["Fecha objetivo"])})
    unique_names(goals, "name", "Objetivos")
    savings_accounts = [item for item in accounts if item["type"] == "SAVINGS" and (item["institution"] or "").lower() == "virtual"]
    funded_total = sum((item["funded"] for item in goals), Decimal("0"))
    if funded_total > 0 and len(savings_accounts) != 1:
        raise ValueError("Objetivos: hace falta una única cuenta de ahorro virtual")
    savings_account_name = savings_accounts[0]["name"] if savings_accounts else None
    if savings_accounts and funded_total > savings_accounts[0]["expected_balance"]:
        raise ValueError("Objetivos: el ahorro supera el saldo de la cuenta virtual")

    savings_percent = None
    for movement in movements:
        match = re.search(r"ahorro\s+(\d+(?:[,.]\d+)?)\s*%", movement["concept"], re.IGNORECASE)
        if match and movement["type"] == "TRANSFER" and movement["destination"] == savings_account_name:
            value = Decimal(match.group(1).replace(",", "."))
            if 0 < value <= 100:
                savings_percent = value
    return TemplateData(
        accounts=accounts, categories=categories,
        movements=movements, budgets=budgets, fixed_expenses=fixed_expenses,
        incomes=incomes, goals=goals, savings_percent=savings_percent,
        last_movement=last_movement, savings_account_name=savings_account_name,
    )


def import_template(db: Session, user_id: int, data: TemplateData) -> dict[str, int]:
    if db.get(User, user_id) is None:
        raise ValueError("El usuario no existe. Regístralo primero en la aplicación")
    models = (Account, Transaction, Budget, IncomeSource, RecurringExpense,
              ScheduledExpense, SavingsGoal)
    if any(db.scalar(select(func.count()).select_from(model).where(model.user_id == user_id)) for model in models):
        raise ValueError("El usuario ya tiene datos financieros; la importación requiere una cuenta vacía para evitar duplicados")
    existing_categories = list(db.scalars(select(Category).where(Category.user_id == user_id)))
    if any(item.parent_id is not None or item.name not in data.categories for item in existing_categories):
        raise ValueError("El usuario tiene categorías propias; revisa la importación antes de mezclar datos")

    accounts: dict[str, Account] = {}
    for row in data.accounts:
        item = Account(user_id=user_id, name=row["name"], type=row["type"],
                       institution=row["institution"], initial_balance=row["initial_balance"],
                       currency="EUR", active=row["active"], notes=row["notes"])
        db.add(item)
        db.flush()
        accounts[item.name] = item

    categories: dict[str, Category] = {item.name: item for item in existing_categories}
    for name in data.categories:
        if name not in categories:
            item = Category(user_id=user_id, name=name, parent_id=None)
            db.add(item)
            db.flush()
            categories[name] = item
    subcategories: dict[tuple[str, str], Category] = {}
    for movement in data.movements:
        parent, child = movement["category"], movement["subcategory"]
        if parent and child and (parent, child) not in subcategories:
            item = Category(user_id=user_id, name=child, parent_id=categories[parent].id)
            db.add(item)
            db.flush()
            subcategories[(parent, child)] = item

    transactions: list[tuple[dict, Transaction]] = []
    for row in data.movements:
        category = subcategories.get((row["category"], row["subcategory"])) if row["subcategory"] else categories.get(row["category"])
        item = Transaction(
            user_id=user_id, date=row["date"], type=row["type"],
            source_account_id=accounts[row["source"]].id if row["source"] else None,
            destination_account_id=accounts[row["destination"]].id if row["destination"] else None,
            category_id=category.id if category else None, concept=row["concept"],
            amount=row["amount"], payment_method=row["payment_method"],
            is_fixed=row["is_fixed"], is_necessary=row["is_necessary"],
            notes=row["notes"], status="CLEARED", reconciliation=row["reconciliation"],
        )
        db.add(item)
        db.flush()
        transactions.append((row, item))

    actual_balances = account_balances(db, user_id, data.last_movement)
    for row in data.accounts:
        if actual_balances[accounts[row["name"]].id] != row["expected_balance"]:
            raise ValueError(f"El saldo importado de {row['name']} no coincide con el Excel")

    for row in data.budgets:
        db.add(Budget(user_id=user_id, category_id=categories[row["category"]].id,
                      period="MONTH", currency="EUR", amount=row["amount"], active=True))

    for row in data.fixed_expenses:
        if row["frequency"] == "Mensual":
            start = row["start"] or month_day(data.last_movement.year, data.last_movement.month, row["due_day"])
            recurring = RecurringExpense(
                user_id=user_id, name=row["name"], amount=row["amount"],
                account_id=accounts[row["account"]].id,
                category_id=categories[row["category"]].id,
                frequency="MONTHLY", starts_on=start, ends_on=row["end"], active=row["active"],
            )
            db.add(recurring)
            db.flush()
            if row["active"]:
                for source, movement in transactions:
                    if (source["type"] == "EXPENSE" and source["concept"] == row["name"]
                            and source["source"] == row["account"]
                            and start - timedelta(days=2) <= source["date"] <= start):
                        db.add(RecurringPayment(user_id=user_id, expense_id=recurring.id,
                                                due_date=start, transaction_id=movement.id))
                        break
        else:
            db.add(ScheduledExpense(
                user_id=user_id, name=row["name"], amount=row["amount"],
                account_id=accounts[row["account"]].id,
                category_id=categories[row["category"]].id,
                due_date=row["start"], status="PLANNED" if row["active"] else "CANCELLED",
                transaction_id=None,
            ))

    for index, row in enumerate(data.incomes):
        matching = [(source, movement) for source, movement in transactions
                    if source["type"] == "INCOME" and source["destination"] == row["account"]
                    and row["name"].lower() in source["concept"].lower()]
        starts_on = min((source["date"] for source, _ in matching), default=data.last_movement)
        item = IncomeSource(user_id=user_id, name=row["name"], amount=row["amount"],
                            account_id=accounts[row["account"]].id,
                            day_rule="LAST_DAY_OF_MONTH", day_of_month=None,
                            starts_on=starts_on, ends_on=None, active=row["active"], is_primary=index == 0)
        db.add(item)
        db.flush()
        for source, movement in matching:
            if source["date"] == income_day(source["date"].year, source["date"].month, "LAST_DAY_OF_MONTH", None):
                db.add(IncomeReceipt(user_id=user_id, source_id=item.id,
                                     due_date=source["date"], transaction_id=movement.id))

    if data.savings_percent and data.incomes:
        primary = db.scalar(select(IncomeSource).where(IncomeSource.user_id == user_id, IncomeSource.is_primary == True))
        db.add(SavingsRule(user_id=user_id, name="Ahorro del Excel",
                           income_source_id=primary.id, mode="PERCENT",
                           value=data.savings_percent, active=True))

    savings_account = accounts.get(data.savings_account_name) if data.savings_account_name else None
    transfer_dates = [row["date"] for row, _ in transactions
                      if row["type"] == "TRANSFER" and row["destination"] == data.savings_account_name]
    contribution_date = max(transfer_dates, default=data.last_movement)
    ordered_goals = sorted(data.goals, key=lambda row: (row["due_date"] is None, row["due_date"] or date.max, row["name"]))
    for priority, row in enumerate(ordered_goals, 1):
        goal = SavingsGoal(user_id=user_id, name=row["name"], target_amount=row["target"],
                           currency="EUR", priority=priority, due_date=row["due_date"], active=True)
        db.add(goal)
        db.flush()
        if row["funded"] > 0:
            db.add(Reservation(user_id=user_id, account_id=savings_account.id,
                               goal_id=goal.id, amount=row["funded"]))
            db.add(GoalContribution(user_id=user_id, goal_id=goal.id,
                                    account_id=savings_account.id, date=contribution_date,
                                    amount=row["funded"], notes="Importado del Excel; fecha tomada de la transferencia a ahorro"))
    if savings_account:
        unallocated = next(row["expected_balance"] for row in data.accounts if row["name"] == savings_account.name) - sum((row["funded"] for row in data.goals), Decimal("0"))
        if unallocated > 0:
            db.add(Reservation(user_id=user_id, account_id=savings_account.id,
                               goal_id=None, amount=unallocated))
    db.flush()
    return {
        "accounts": len(data.accounts), "categories": len(categories) + len(subcategories),
        "transactions": len(transactions), "budgets": len(data.budgets),
        "planned_expenses": len(data.fixed_expenses), "income_sources": len(data.incomes),
        "goals": len(data.goals),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validar o importar la plantilla de finanzas personales")
    parser.add_argument("--file", required=True, type=Path, help="Ruta al XLSX")
    parser.add_argument("--user-id", type=int, help="ID del usuario registrado")
    parser.add_argument("--apply", action="store_true", help="Guardar los datos tras validarlos")
    args = parser.parse_args()
    if args.apply and not args.user_id:
        parser.error("--apply requiere --user-id")
    data = read_template(args.file)
    print("Archivo válido:", data.counts())
    print("Los saldos por cuenta coinciden con el Excel. Las hojas de resumen y proyecciones no crean movimientos.")
    if not args.apply:
        return
    with SessionLocal.begin() as db:
        counts = import_template(db, args.user_id, data)
    print("Importación terminada:", counts)


if __name__ == "__main__":
    main()
