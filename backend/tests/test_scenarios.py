from datetime import date


def test_simulation_compares_without_creating_transactions(client, auth, monkeypatch):
    monkeypatch.setattr("app.api.forecast.user_today", lambda db, user_id: date(2026, 2, 1))
    account = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "initial_balance": "100.00", "currency": "EUR",
    }).json()["id"]
    scheduled = client.post("/api/v1/scheduled-expenses", headers=auth, json={
        "name": "Alquiler", "amount": "20.00", "account_id": account, "due_date": "2026-02-03",
    })
    assert scheduled.status_code == 201, scheduled.text
    base = client.get("/api/v1/forecast?days=5", headers=auth).json()
    assert base["days"][-1]["totals_by_currency"]["EUR"] == "80.00"
    payload = {
        "name": "Compra e ingresos", "overrides": [{"key": base["events"][0]["key"], "amount": "-40.00"}],
        "events": [
            {"date": "2026-02-02", "account_id": account, "amount": "-10.00", "label": "Compra"},
            {"date": "2026-02-04", "account_id": account, "amount": "50.00", "label": "Extra"},
        ],
    }
    simulation = client.post("/api/v1/scenarios/simulate?days=5", headers=auth, json=payload)
    assert simulation.status_code == 200, simulation.text
    result = simulation.json()
    assert result["days"][-1]["scenario_by_currency"]["EUR"] == "100.00"
    assert result["final_difference_by_currency"]["EUR"] == "20.00"
    assert result["minimum_scenario_by_currency"]["EUR"] == "50.00"
    assert result["days"][-1]["baseline_by_currency"]["EUR"] == "80.00"
    assert client.get("/api/v1/transactions", headers=auth).json()["total"] == 0
    assert client.get("/api/v1/accounts/{}/balance".format(account), headers=auth).json()["balance"] == "100.00"

    saved = client.post("/api/v1/scenarios", headers=auth, json=payload)
    assert saved.status_code == 201, saved.text
    item_id = saved.json()["id"]
    assert len(client.get("/api/v1/scenarios", headers=auth).json()) == 1
    compared = client.get(f"/api/v1/scenarios/{item_id}/compare?days=5", headers=auth)
    assert compared.status_code == 200, compared.text
    assert compared.json()["final_difference_by_currency"]["EUR"] == "20.00"
    edited = client.patch(f"/api/v1/scenarios/{item_id}", headers=auth, json={
        "name": "Sin compra", "overrides": [], "events": [],
    })
    assert edited.status_code == 200, edited.text
    assert client.get(f"/api/v1/scenarios/{item_id}/compare?days=5", headers=auth).json()["final_difference_by_currency"]["EUR"] == "0.00"
    assert client.delete(f"/api/v1/scenarios/{item_id}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/scenarios/{item_id}", headers=auth).status_code == 404


def test_scenarios_validate_accounts_and_isolate_users(client, auth):
    account = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "currency": "EUR",
    }).json()["id"]
    second = client.post("/api/v1/auth/register", json={
        "email": "scenarios-other@example.com", "password": "another-strong-password",
    })
    other_auth = {"Authorization": f"Bearer {second.json()['access_token']}"}
    payload = {"name": "Caso", "events": [
        {"date": "2026-12-01", "account_id": account, "amount": "-10", "label": "Prueba"},
    ]}
    assert client.post("/api/v1/scenarios", headers=other_auth, json=payload).status_code == 422
    created = client.post("/api/v1/scenarios", headers=auth, json=payload)
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    assert client.get(f"/api/v1/scenarios/{item_id}", headers=other_auth).status_code == 404
    assert client.delete(f"/api/v1/scenarios/{item_id}", headers=other_auth).status_code == 404
    duplicate = {"name": "Duplicado", "overrides": [{"key": "x", "amount": "1"}, {"key": "x", "amount": "2"}]}
    assert client.post("/api/v1/scenarios/simulate", headers=auth, json=duplicate).status_code == 422


def test_hypothetical_savings_reduce_available_not_balance(client, auth, monkeypatch):
    monkeypatch.setattr("app.api.forecast.user_today", lambda db, user_id: date(2026, 2, 1))
    account = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "initial_balance": "100.00", "currency": "EUR",
    }).json()["id"]
    income = client.post("/api/v1/income-sources", headers=auth, json={
        "name": "Nómina", "amount": "200.00", "account_id": account,
        "day_rule": "FIXED_DAY", "day_of_month": 3, "starts_on": "2026-01-01",
    })
    assert income.status_code == 201, income.text
    comparison = client.post("/api/v1/scenarios/simulate?days=5", headers=auth, json={
        "name": "Ahorro al 40%", "savings_percent": "40",
    })
    assert comparison.status_code == 200, comparison.text
    result = comparison.json()
    assert result["days"][-1]["scenario_by_currency"]["EUR"] == "300.00"
    assert result["days"][-1]["baseline_by_currency"]["EUR"] == "300.00"
    assert result["simulated_savings_by_currency"]["EUR"] == "80.00"
    assert result["days"][-1]["scenario_available_by_currency"]["EUR"] == "220.00"
    assert client.get(f"/api/v1/accounts/{account}/balance", headers=auth).json()["balance"] == "100.00"


def test_saved_scenario_ignores_inactive_account_event(client, auth, monkeypatch):
    monkeypatch.setattr("app.api.forecast.user_today", lambda db, user_id: date(2026, 2, 1))
    account = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "currency": "EUR",
    }).json()["id"]
    scenario = client.post("/api/v1/scenarios", headers=auth, json={
        "name": "Compra", "events": [{
            "date": "2026-02-02", "account_id": account, "amount": "-10.00", "label": "Prueba",
        }],
    })
    assert scenario.status_code == 201, scenario.text
    assert client.patch(f"/api/v1/accounts/{account}", headers=auth, json={"active": False}).status_code == 200
    compared = client.get(f"/api/v1/scenarios/{scenario.json()['id']}/compare?days=5", headers=auth)
    assert compared.status_code == 200, compared.text
    assert compared.json()["ignored_events"] == 1
