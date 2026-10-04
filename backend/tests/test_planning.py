from datetime import date

from app.application.calendar import income_dates, month_day, recurring_dates


def account(client, auth):
    response = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "currency": "EUR",
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def movement(client, auth, kind, account_id, amount="30.00"):
    response = client.post("/api/v1/transactions", headers=auth, json={
        "date": "2026-02-28", "type": kind, "concept": "Pago real", "amount": amount,
        "source_account_id": account_id if kind == "EXPENSE" else None,
        "destination_account_id": account_id if kind == "INCOME" else None,
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_calendar_month_end_leap_year_and_weekly():
    assert month_day(2028, 2, 31) == date(2028, 2, 29)
    assert income_dates(date(2026, 8, 1), date(2026, 8, 31), "FIRST_BUSINESS_DAY", None, date(2026, 1, 1)) == [date(2026, 8, 3)]
    assert income_dates(date(2028, 2, 1), date(2028, 3, 31), "FIXED_DAY", 31, date(2028, 1, 1)) == [date(2028, 2, 29), date(2028, 3, 31)]
    assert recurring_dates(date(2026, 2, 4), date(2026, 2, 20), "WEEKLY", date(2026, 1, 28)) == [
        date(2026, 2, 4), date(2026, 2, 11), date(2026, 2, 18),
    ]


def test_planning_and_upcoming_linked_transactions(client, auth):
    bank = account(client, auth)
    income = client.post("/api/v1/income-sources", headers=auth, json={
        "name": "Nómina", "amount": "2000.00", "account_id": bank,
        "day_rule": "LAST_DAY_OF_MONTH", "starts_on": "2026-01-01", "is_primary": True,
    })
    assert income.status_code == 201, income.text
    recurring = client.post("/api/v1/recurring-expenses", headers=auth, json={
        "name": "Alquiler", "amount": "600.00", "account_id": bank,
        "frequency": "MONTHLY", "starts_on": "2026-01-31",
    })
    assert recurring.status_code == 201, recurring.text
    scheduled = client.post("/api/v1/scheduled-expenses", headers=auth, json={
        "name": "Seguro", "amount": "90.00", "account_id": bank, "due_date": "2026-01-15",
    })
    assert scheduled.status_code == 201, scheduled.text
    debt = client.post("/api/v1/debts", headers=auth, json={
        "name": "Préstamo", "principal": "100.00", "installment_amount": "40.00",
        "account_id": bank, "starts_on": "2026-01-01", "due_day": 15,
    })
    assert debt.status_code == 201, debt.text
    upcoming = client.get("/api/v1/upcoming?date_from=2026-02-01&days=59", headers=auth)
    assert upcoming.status_code == 200, upcoming.text
    events = upcoming.json()
    assert ("INCOME", "2026-02-28") in {(item["kind"], item["date"]) for item in events}
    assert ("RECURRING", "2026-02-28") in {(item["kind"], item["date"]) for item in events}
    assert any(item["kind"] == "SCHEDULED" and item["overdue"] for item in events)

    incoming = movement(client, auth, "INCOME", bank, "2000.00")
    receipt = client.post(f"/api/v1/income-sources/{income.json()['id']}/receipts", headers=auth, json={
        "due_date": "2026-02-28", "transaction_id": incoming,
    })
    assert receipt.status_code == 201, receipt.text
    rent = movement(client, auth, "EXPENSE", bank, "600.00")
    paid = client.post(f"/api/v1/recurring-expenses/{recurring.json()['id']}/payments", headers=auth, json={
        "due_date": "2026-02-28", "transaction_id": rent,
    })
    assert paid.status_code == 201, paid.text
    assert client.delete(f"/api/v1/transactions/{rent}", headers=auth).status_code == 409
    events = client.get("/api/v1/upcoming?date_from=2026-02-01&days=59", headers=auth).json()
    assert not any(item["kind"] == "INCOME" and item["date"] == "2026-02-28" for item in events)
    assert not any(item["kind"] == "RECURRING" and item["date"] == "2026-02-28" for item in events)

    loan_payment = movement(client, auth, "EXPENSE", bank)
    response = client.post(f"/api/v1/debts/{debt.json()['id']}/payments", headers=auth, json={"transaction_id": loan_payment})
    assert response.status_code == 201, response.text
    assert response.json()["remaining"] == "70.00"
    assert client.post(f"/api/v1/debts/{debt.json()['id']}/payments", headers=auth, json={"transaction_id": loan_payment}).status_code == 409
    assert client.post(f"/api/v1/scheduled-expenses/{scheduled.json()['id']}/pay", headers=auth, json={"transaction_id": loan_payment}).status_code == 409
    links = client.get("/api/v1/planning-links", headers=auth).json()
    assert len(links) == 3
    debt_link = next(item for item in links if item["kind"] == "DEBT")
    assert client.delete(f"/api/v1/debts/{debt.json()['id']}/payments/{debt_link['id']}", headers=auth).status_code == 200
    assert client.delete(f"/api/v1/transactions/{loan_payment}", headers=auth).status_code == 204


def test_planning_isolation_and_validation(client, auth):
    bank = account(client, auth)
    other = client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "another-strong-password"})
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}
    payload = {"name": "Pago", "amount": "10.00", "account_id": bank, "due_date": "2026-03-01"}
    assert client.post("/api/v1/scheduled-expenses", headers=other_auth, json=payload).status_code == 404
    assert client.post("/api/v1/scheduled-expenses", headers=auth, json={**payload, "amount": "-10.00"}).status_code == 422
    created = client.post("/api/v1/scheduled-expenses", headers=auth, json=payload).json()
    assert client.patch(f"/api/v1/scheduled-expenses/{created['id']}", headers=auth, json={"status": "PAID"}).status_code == 422
    assert client.patch(f"/api/v1/scheduled-expenses/{created['id']}", headers=other_auth, json={"name": "Otro"}).status_code == 404


def test_delete_planning_rules_preserves_real_movements(client, auth):
    bank = account(client, auth)
    income = client.post("/api/v1/income-sources", headers=auth, json={
        "name": "Nómina", "amount": "2000.00", "account_id": bank,
        "day_rule": "LAST_DAY_OF_MONTH", "starts_on": "2026-01-01",
    }).json()
    recurring = client.post("/api/v1/recurring-expenses", headers=auth, json={
        "name": "Alquiler", "amount": "600.00", "account_id": bank,
        "frequency": "MONTHLY", "starts_on": "2026-01-31",
    }).json()
    scheduled = client.post("/api/v1/scheduled-expenses", headers=auth, json={
        "name": "Seguro", "amount": "90.00", "account_id": bank, "due_date": "2026-02-15",
    }).json()
    debt = client.post("/api/v1/debts", headers=auth, json={
        "name": "Préstamo", "principal": "100.00", "installment_amount": "40.00",
        "account_id": bank, "starts_on": "2026-01-01", "due_day": 15,
    }).json()
    savings_rule = client.post("/api/v1/savings-rules", headers=auth, json={
        "name": "Guardar", "income_source_id": income["id"], "mode": "PERCENT", "value": "10.00",
    })
    assert savings_rule.status_code == 201, savings_rule.text

    linked = [
        ("income-sources", income["id"], movement(client, auth, "INCOME", bank, "2000.00"), "receipts", {"due_date": "2026-02-28"}),
        ("recurring-expenses", recurring["id"], movement(client, auth, "EXPENSE", bank, "600.00"), "payments", {"due_date": "2026-02-28"}),
        ("scheduled-expenses", scheduled["id"], movement(client, auth, "EXPENSE", bank, "90.00"), "pay", {}),
        ("debts", debt["id"], movement(client, auth, "EXPENSE", bank, "40.00"), "payments", {}),
    ]
    for path, item_id, transaction_id, link_path, body in linked:
        response = client.post(f"/api/v1/{path}/{item_id}/{link_path}", headers=auth, json={
            "transaction_id": transaction_id, **body,
        })
        assert response.status_code in (200, 201), response.text

    other = client.post("/api/v1/auth/register", json={"email": "other-delete@example.com", "password": "another-strong-password"})
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}
    for path, item_id, transaction_id, _, _ in linked:
        assert client.delete(f"/api/v1/{path}/{item_id}", headers=other_auth).status_code == 404
        assert client.delete(f"/api/v1/{path}/{item_id}", headers=auth).status_code == 204
        assert client.get(f"/api/v1/{path}", headers=auth).json() == []
        assert client.get(f"/api/v1/transactions/{transaction_id}", headers=auth).status_code == 200
        assert client.delete(f"/api/v1/{path}/{item_id}", headers=auth).status_code == 404
    assert client.get("/api/v1/planning-links", headers=auth).json() == []
    assert client.get("/api/v1/savings-rules", headers=auth).json() == []
