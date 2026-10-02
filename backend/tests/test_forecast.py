from datetime import date
from decimal import Decimal

from app.application.forecast import CashEvent, project


def test_pure_projection_is_ordered_and_does_not_mutate_initial():
    start = date(2026, 2, 1)
    initial = {1: Decimal("100.00")}
    events = [
        CashEvent(date(2026, 2, 3), 1, Decimal("40.00"), "b", "Ingreso"),
        CashEvent(start, 1, Decimal("-20.00"), "a", "Gasto"),
    ]
    result = project(initial, events, start, date(2026, 2, 3))
    assert [day.balances[1] for day in result] == [Decimal("80.00"), Decimal("80.00"), Decimal("120.00")]
    assert initial[1] == Decimal("100.00")


def test_forecast_and_salary_cycle(client, auth, monkeypatch):
    monkeypatch.setattr("app.api.forecast.user_today", lambda db, user_id: date(2026, 2, 1))
    bank = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "initial_balance": "100.00", "currency": "EUR",
    }).json()["id"]
    income = client.post("/api/v1/income-sources", headers=auth, json={
        "name": "Nómina", "amount": "200.00", "account_id": bank, "day_rule": "FIXED_DAY",
        "day_of_month": 15, "starts_on": "2026-01-01", "is_primary": True,
    })
    assert income.status_code == 201, income.text
    expense = client.post("/api/v1/recurring-expenses", headers=auth, json={
        "name": "Factura", "amount": "20.00", "account_id": bank,
        "frequency": "MONTHLY", "starts_on": "2026-01-05",
    })
    assert expense.status_code == 201, expense.text
    one_off = client.post("/api/v1/scheduled-expenses", headers=auth, json={
        "name": "Seguro", "amount": "10.00", "account_id": bank, "due_date": "2026-02-08",
    })
    assert one_off.status_code == 201, one_off.text
    pending = client.post("/api/v1/transactions", headers=auth, json={
        "date": "2026-02-10", "type": "EXPENSE", "source_account_id": bank,
        "concept": "Pendiente", "amount": "7.00", "status": "PENDING",
    })
    assert pending.status_code == 201, pending.text
    cycle = client.get("/api/v1/salary-cycles", headers=auth).json()
    assert cycle["current_start"] == "2026-01-15"
    assert cycle["current_end"] == "2026-02-14"
    assert cycle["next_payday"] == "2026-02-15"
    response = client.get("/api/v1/forecast?days=20", headers=auth)
    assert response.status_code == 200, response.text
    forecast = response.json()
    assert forecast["days"][-1]["totals_by_currency"]["EUR"] == "263.00"
    assert forecast["minimum_until_payday_by_currency"]["EUR"] == "63.00"
    assert len(forecast["events"]) == 4


def test_current_month_overdue_recurring_is_projected_once(client, auth, monkeypatch):
    monkeypatch.setattr("app.api.forecast.user_today", lambda db, user_id: date(2026, 2, 2))
    monkeypatch.setattr("app.api.planning.user_today", lambda db, user_id: date(2026, 2, 2))
    account = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "initial_balance": "100.00", "currency": "EUR",
    }).json()["id"]
    ids = {}
    for name, amount in (("Pendiente", "20.00"), ("Pagado", "10.00")):
        response = client.post("/api/v1/recurring-expenses", headers=auth, json={
            "name": name, "amount": amount, "account_id": account,
            "frequency": "MONTHLY", "starts_on": "2026-02-01",
        })
        assert response.status_code == 201, response.text
        ids[name] = response.json()["id"]
    movement = client.post("/api/v1/transactions", headers=auth, json={
        "date": "2026-02-01", "type": "EXPENSE", "source_account_id": account,
        "concept": "Pagado", "amount": "10.00", "status": "CLEARED",
    })
    assert movement.status_code == 201, movement.text
    linked = client.post(f"/api/v1/recurring-expenses/{ids['Pagado']}/payments", headers=auth, json={
        "due_date": "2026-02-01", "transaction_id": movement.json()["id"],
    })
    assert linked.status_code == 201, linked.text
    forecast = client.get("/api/v1/forecast?days=2", headers=auth)
    assert forecast.status_code == 200, forecast.text
    result = forecast.json()
    assert result["days"][0]["totals_by_currency"]["EUR"] == "70.00"
    assert len(result["events"]) == 1
    assert result["events"][0]["label"] == "Pendiente"
