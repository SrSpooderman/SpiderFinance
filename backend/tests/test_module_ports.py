"""Unit tests for cross-domain reads supplied through ports."""

from datetime import date
from decimal import Decimal

import pytest

from app.infrastructure.models import Debt
from app.modules.budgets.infrastructure import SqlBudgetStore
from app.modules.forecasting.infrastructure import SqlForecastReader
from app.modules.imports.infrastructure import SqlImportStore
from app.modules.investments.infrastructure import SqlInvestmentStore
from app.modules.planning.write_infrastructure import SqlPlanningStore
from app.modules.reporting.infrastructure import SqlDashboardReader
from app.modules.savings.infrastructure import SqlSavingsStore


class LedgerReaderStub:
    def __init__(self):
        self.calls = []

    def today(self, user_id):
        self.calls.append(("today", user_id))
        return date(2026, 2, 1)

    def account(self, user_id, account_id):
        self.calls.append(("account", user_id, account_id))
        return {"id": account_id, "user_id": user_id}

    def category(self, user_id, category_id):
        self.calls.append(("category", user_id, category_id))
        return {"id": category_id, "user_id": user_id}

    def balance(self, user_id, account_id, as_of=None):
        self.calls.append(("balance", user_id, account_id, as_of))
        return Decimal("12.50")

    def balances(self, user_id, as_of=None):
        self.calls.append(("balances", user_id, as_of))
        return {4: Decimal("12.50")}


@pytest.mark.parametrize("store_type,method,args,expected,call", [
    (SqlBudgetStore, "today", (7,), date(2026, 2, 1), ("today", 7)),
    (SqlBudgetStore, "category", (7, 8), {"id": 8, "user_id": 7}, ("category", 7, 8)),
    (SqlDashboardReader, "balances", (7, date(2026, 2, 1)), {4: Decimal("12.50")},
     ("balances", 7, date(2026, 2, 1))),
    (SqlForecastReader, "balances", (7, date(2026, 2, 1)), {4: Decimal("12.50")},
     ("balances", 7, date(2026, 2, 1))),
    (SqlImportStore, "balances", (7,), {4: Decimal("12.50")}, ("balances", 7, None)),
    (SqlSavingsStore, "account_balance", (7, 4), Decimal("12.50"), ("balance", 7, 4, None)),
    (SqlPlanningStore, "account", (7, 4), {"id": 4, "user_id": 7}, ("account", 7, 4)),
    (SqlInvestmentStore, "account", (7, 4), {"id": 4, "user_id": 7}, ("account", 7, 4)),
])
def test_sql_read_models_use_injected_ledger(store_type, method, args, expected, call):
    ledger = LedgerReaderStub()
    store = (SqlInvestmentStore(object(), ledger, object()) if store_type is SqlInvestmentStore
             else store_type(object(), ledger))

    assert getattr(store, method)(*args) == expected
    assert ledger.calls == [call]


def test_investment_debt_projection_uses_planning_port():
    debt = Debt(id=3, user_id=7, name="Préstamo", principal=Decimal("100"),
                installment_amount=Decimal("10"), account_id=4, starts_on=date(2026, 1, 1),
                due_day=1, active=True)

    class SessionStub:
        def scalars(self, query):
            return [debt]

    class PlanningStub:
        def __init__(self):
            self.calls = []

        def debt_remaining(self, user_id, debt_id, principal):
            self.calls.append((user_id, debt_id, principal))
            return Decimal("60")

    planning = PlanningStub()
    store = SqlInvestmentStore(SessionStub(), LedgerReaderStub(), planning)

    assert store.debts(7)[0]["remaining"] == Decimal("60")
    assert planning.calls == [(7, 3, Decimal("100"))]
