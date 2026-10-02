from datetime import date, timedelta


def account(client, auth, name, initial="0.00", currency="EUR"):
    response = client.post("/api/v1/accounts", headers=auth, json={
        "name": name, "type": "CHECKING", "initial_balance": initial, "currency": currency,
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def movement(client, auth, kind, amount, source=None, destination=None, status="CLEARED", day=None):
    response = client.post("/api/v1/transactions", headers=auth, json={
        "date": (day or date.today()).isoformat(), "type": kind, "source_account_id": source,
        "destination_account_id": destination, "concept": kind, "amount": amount, "status": status,
    })
    return response


def balance(client, auth, account_id):
    return client.get(f"/api/v1/accounts/{account_id}/balance", headers=auth).json()["balance"]


def test_account_balance_transfer_and_reconciliation(client, auth):
    checking = account(client, auth, "Corriente", "1000.00")
    savings = account(client, auth, "Ahorros", "50.00")
    assert movement(client, auth, "INCOME", "200.00", destination=checking).status_code == 201
    assert movement(client, auth, "EXPENSE", "75.00", source=checking).status_code == 201
    assert movement(client, auth, "TRANSFER", "300.00", source=checking, destination=savings).status_code == 201
    assert balance(client, auth, checking) == "825.00"
    assert balance(client, auth, savings) == "350.00"
    summary = client.get("/api/v1/dashboard", headers=auth).json()
    assert summary["balances"][0]["total"] == "1175.00"
    adjustment = client.post(f"/api/v1/accounts/{checking}/reconcile", headers=auth, json={
        "date": date.today().isoformat(), "observed_balance": "819.00", "notes": "Saldo del banco",
    })
    assert adjustment.status_code == 200, adjustment.text
    assert adjustment.json()["difference"] == "-6.00"
    assert adjustment.json()["transaction"]["reconciliation"] is True
    assert balance(client, auth, checking) == "819.00"
    assert balance(client, auth, savings) == "350.00"


def test_transfer_to_reserved_savings_changes_source_and_available_not_total(client, auth):
    checking = account(client, auth, "Personal")
    response = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Ahorros", "type": "SAVINGS", "initial_balance": "0.00", "currency": "EUR",
    })
    assert response.status_code == 201, response.text
    savings = response.json()["id"]
    assert movement(client, auth, "INCOME", "1450.00", destination=checking).status_code == 201
    assert movement(client, auth, "TRANSFER", "507.50", source=checking, destination=savings).status_code == 201
    assert balance(client, auth, checking) == "942.50"
    assert balance(client, auth, savings) == "507.50"
    goal = client.post("/api/v1/goals", headers=auth, json={
        "name": "Ahorro", "target_amount": "1000.00", "currency": "EUR",
    })
    assert goal.status_code == 201, goal.text
    reservation = client.post(f"/api/v1/goals/{goal.json()['id']}/contributions", headers=auth, json={
        "account_id": savings, "amount": "507.50", "date": date.today().isoformat(),
    })
    assert reservation.status_code == 201, reservation.text
    summary = client.get("/api/v1/dashboard", headers=auth).json()["balances"][0]
    assert summary["total"] == "1450.00"
    assert summary["savings"] == "507.50"
    assert summary["reserved"] == "507.50"
    assert summary["available"] == "942.50"


def test_pending_and_future_do_not_change_current_balance(client, auth):
    current = account(client, auth, "Corriente", "100.00")
    assert movement(client, auth, "EXPENSE", "20.00", source=current, status="PENDING").status_code == 201
    assert movement(client, auth, "EXPENSE", "30.00", source=current, day=date.today() + timedelta(days=2)).status_code == 201
    assert balance(client, auth, current) == "100.00"


def test_validation_and_user_isolation(client, auth):
    mine = account(client, auth, "Mía", "100.00")
    second = client.post("/api/v1/auth/register", json={"email": "dos@example.com", "password": "another-strong-password"})
    other_auth = {"Authorization": f"Bearer {second.json()['access_token']}"}
    assert client.get(f"/api/v1/accounts/{mine}", headers=other_auth).status_code == 404
    assert movement(client, other_auth, "EXPENSE", "1.00", source=mine).status_code == 404
    assert movement(client, auth, "TRANSFER", "5.00", source=mine, destination=mine).status_code == 422
    assert movement(client, auth, "EXPENSE", "-1.00", source=mine).status_code == 422
    usd = account(client, auth, "USD", currency="USD")
    assert movement(client, auth, "TRANSFER", "5.00", source=mine, destination=usd).status_code == 422


def test_transaction_filters_and_corrections(client, auth):
    checking = account(client, auth, "Corriente", "100.00")
    first = movement(client, auth, "EXPENSE", "12.50", source=checking).json()
    movement(client, auth, "INCOME", "30.00", destination=checking)
    filtered = client.get("/api/v1/transactions?type=EXPENSE&page_size=1", headers=auth).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == first["id"]
    response = client.patch(f"/api/v1/transactions/{first['id']}", headers=auth, json={"amount": "10.00"})
    assert response.status_code == 200, response.text
    assert balance(client, auth, checking) == "120.00"
    assert client.delete(f"/api/v1/transactions/{first['id']}", headers=auth).status_code == 204
    assert balance(client, auth, checking) == "130.00"
