"""Creates the fictional, read-only sample workspace for public demo instances."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.infrastructure.models import (
    Account, Budget, Category, GoalContribution, IncomeSource, InvestmentPosition,
    RecurringExpense, SavingsGoal, Scenario, Transaction, User, UserSettings,
)
from app.modules.identity.domain import DEFAULT_CATEGORIES


def ensure_demo_data() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == "demo@spiderfinance.com")):
            return

        user = User(email="demo@spiderfinance.com", password_hash=hash_password("demo-instance-no-password-login"))
        db.add(user)
        db.flush()
        user_id = user.id
        db.add(UserSettings(user_id=user_id, currency="EUR", locale="es-ES", timezone="Europe/Madrid", theme="light-teal"))
        categories = {name: Category(user_id=user_id, name=name) for name in DEFAULT_CATEGORIES}
        db.add_all(categories.values())
        db.flush()

        checking = Account(user_id=user_id, name="Cuenta principal", type="CHECKING", institution="Banco del Sol", initial_balance=Decimal("2450.00"), currency="EUR", active=True, notes="Cuenta ficticia de demostración")
        savings = Account(user_id=user_id, name="Ahorro", type="SAVINGS", institution="Banco del Sol", initial_balance=Decimal("6200.00"), currency="EUR", active=True)
        broker = Account(user_id=user_id, name="Cartera indexada", type="INVESTMENT", institution="Horizonte Inversiones", initial_balance=Decimal("850.00"), currency="EUR", active=True)
        db.add_all([checking, savings, broker])
        db.flush()

        today = date.today()
        transactions = []
        monthly = [
            ("Alquiler", "EXPENSE", "780.00", "Hogar"),
            ("Compra semanal", "EXPENSE", "86.42", "Alimentación"),
            ("Abono transporte", "EXPENSE", "32.00", "Transporte"),
            ("Internet y móvil", "EXPENSE", "46.90", "Suscripciones"),
            ("Restaurante", "EXPENSE", "38.50", "Restaurantes"),
            ("Compra supermercado", "EXPENSE", "64.20", "Alimentación"),
            ("Cine y ocio", "EXPENSE", "24.00", "Ocio"),
        ]
        for months_ago in range(5, -1, -1):
            month_index = today.year * 12 + today.month - 1 - months_ago
            year, month = divmod(month_index, 12)
            month += 1
            transactions.append(Transaction(user_id=user_id, date=date(year, month, 1), type="INCOME", source_account_id=None, destination_account_id=checking.id, category_id=None, concept="Nómina · Estudio Creativo", amount=Decimal("2850.00"), payment_method="Transferencia", is_fixed=True, is_necessary=True, status="CLEARED", reconciliation=False))
            for day, (concept, kind, amount, category) in enumerate(monthly):
                safe_day = min(3 + day * 3, 27)
                transactions.append(Transaction(user_id=user_id, date=date(year, month, safe_day), type=kind, source_account_id=checking.id, destination_account_id=None, category_id=categories[category].id, concept=concept, amount=Decimal(amount), payment_method="Tarjeta", is_fixed=concept == "Alquiler", is_necessary=category in {"Hogar", "Alimentación", "Transporte"}, status="CLEARED", reconciliation=False))
        db.add_all(transactions)

        emergency = SavingsGoal(user_id=user_id, name="Fondo de emergencia", target_amount=Decimal("10000.00"), currency="EUR", priority=1, due_date=today + timedelta(days=240), active=True)
        holiday = SavingsGoal(user_id=user_id, name="Viaje de verano", target_amount=Decimal("1800.00"), currency="EUR", priority=2, due_date=today + timedelta(days=180), active=True)
        db.add_all([
            IncomeSource(user_id=user_id, name="Nómina", amount=Decimal("2850.00"), account_id=checking.id, day_rule="FIXED_DAY", day_of_month=1, starts_on=today.replace(day=1), active=True, is_primary=True),
            RecurringExpense(user_id=user_id, name="Alquiler", amount=Decimal("780.00"), account_id=checking.id, category_id=categories["Hogar"].id, frequency="MONTHLY", starts_on=today.replace(day=1), active=True),
            RecurringExpense(user_id=user_id, name="Internet y móvil", amount=Decimal("46.90"), account_id=checking.id, category_id=categories["Suscripciones"].id, frequency="MONTHLY", starts_on=today.replace(day=1), active=True),
            emergency,
            holiday,
            Budget(user_id=user_id, category_id=categories["Alimentación"].id, period="MONTH", currency="EUR", amount=Decimal("400.00"), active=True),
            Budget(user_id=user_id, category_id=categories["Ocio"].id, period="MONTH", currency="EUR", amount=Decimal("180.00"), active=True),
            InvestmentPosition(user_id=user_id, account_id=broker.id, name="Índice global", symbol="WORLD", units=Decimal("12.50000000"), cost_basis=Decimal("1100.00"), market_value=Decimal("1284.50"), valued_on=today),
            InvestmentPosition(user_id=user_id, account_id=broker.id, name="Bonos europeos", symbol="EUBD", units=Decimal("8.00000000"), cost_basis=Decimal("760.00"), market_value=Decimal("792.30"), valued_on=today),
        ])
        db.flush()
        db.add_all([
            GoalContribution(user_id=user_id, goal_id=emergency.id, account_id=savings.id, date=today - timedelta(days=14), amount=Decimal("2500.00"), notes="Aportaciones acumuladas de ejemplo"),
            GoalContribution(user_id=user_id, goal_id=holiday.id, account_id=savings.id, date=today - timedelta(days=7), amount=Decimal("640.00"), notes="Aportaciones acumuladas de ejemplo"),
            Scenario(user_id=user_id, name="Aumentar el ahorro mensual", notes="Ejemplo de escenario para explorar el simulador.", changes={"overrides": [], "events": [], "savings_percent": 15}),
        ])
        db.commit()
