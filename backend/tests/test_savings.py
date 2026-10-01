from datetime import date


def test_goals_reservations_rules_and_forecast(client, auth):
    today = date.today().isoformat()
    account_response = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "initial_balance": "100.00", "currency": "EUR",
    })
    assert account_response.status_code == 201, account_response.text
    account_id = account_response.json()["id"]
    goal_response = client.post("/api/v1/goals", headers=auth, json={
        "name": "Emergencias", "target_amount": "80.00", "currency": "EUR", "priority": 1,
    })
    assert goal_response.status_code == 201, goal_response.text
    goal_id = goal_response.json()["id"]
    reservation = client.post(f"/api/v1/goals/{goal_id}/contributions", headers=auth, json={
        "account_id": account_id, "amount": "30.00", "date": today,
    })
    assert reservation.status_code == 201, reservation.text
    reservation_id = reservation.json()["id"]
    assert client.get("/api/v1/goals", headers=auth).json()[0]["funded"] == "30.00"
    assert client.get(f"/api/v1/accounts/{account_id}/balance", headers=auth).json()["balance"] == "100.00"
    assert client.post("/api/v1/reservations", headers=auth, json={
        "account_id": account_id, "amount": "80.00", "date": today,
    }).status_code == 422
    forecast = client.get("/api/v1/forecast?days=1", headers=auth).json()
    assert forecast["reserved_by_currency"]["EUR"] == "30.00"
    assert forecast["available_now_by_currency"]["EUR"] == "70.00"

    source = client.post("/api/v1/income-sources", headers=auth, json={
        "name": "Nómina", "amount": "200.00", "account_id": account_id,
        "day_rule": "FIXED_DAY", "day_of_month": 1, "starts_on": today,
    })
    assert source.status_code == 201, source.text
    rule = client.post("/api/v1/savings-rules", headers=auth, json={
        "name": "Diez por ciento", "income_source_id": source.json()["id"],
        "mode": "PERCENT", "value": "10.00",
    })
    assert rule.status_code == 201, rule.text
    recommendation = client.get("/api/v1/savings-recommendations", headers=auth).json()
    assert recommendation["rules"][0]["amount"] == "20.00"
    assert recommendation["allocations"][0]["amount"] == "20.00"
    assert recommendation["allocations"][0]["goal_id"] == goal_id

    released = client.post(f"/api/v1/reservations/{reservation_id}/release", headers=auth, json={
        "amount": "10.00", "date": today,
    })
    assert released.status_code == 200, released.text
    assert released.json()["amount"] == "20.00"
    assert client.get("/api/v1/goals", headers=auth).json()[0]["funded"] == "20.00"
    assert [item["amount"] for item in client.get("/api/v1/goal-contributions", headers=auth).json()] == ["-10.00", "30.00"]


def test_savings_isolation_and_currency(client, auth):
    today = date.today().isoformat()
    bank = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "initial_balance": "50.00", "currency": "EUR",
    }).json()["id"]
    other = client.post("/api/v1/auth/register", json={"email": "savings-other@example.com", "password": "another-strong-password"})
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}
    goal = client.post("/api/v1/goals", headers=auth, json={
        "name": "Dólares", "target_amount": "100.00", "currency": "USD",
    }).json()["id"]
    payload = {"account_id": bank, "amount": "10.00", "date": today}
    assert client.post(f"/api/v1/goals/{goal}/contributions", headers=auth, json=payload).status_code == 422
    assert client.post(f"/api/v1/goals/{goal}/contributions", headers=other_auth, json=payload).status_code == 404
    assert client.get("/api/v1/goals", headers=other_auth).json() == []
