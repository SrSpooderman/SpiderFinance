from datetime import date


def test_budgets_month_cycle_and_statistics(client, auth):
    today = date.today()
    bank = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Banco", "type": "CHECKING", "currency": "EUR",
    }).json()["id"]
    housing = client.post("/api/v1/categories", headers=auth, json={"name": "Vivienda"}).json()["id"]
    rent = client.post("/api/v1/categories", headers=auth, json={"name": "Alquiler", "parent_id": housing}).json()["id"]
    food = client.post("/api/v1/categories", headers=auth, json={"name": "Comida"}).json()["id"]

    def movement(kind, amount, category=None, status="CLEARED"):
        result = client.post("/api/v1/transactions", headers=auth, json={
            "date": today.isoformat(), "type": kind, "concept": kind,
            "amount": amount, "category_id": category, "status": status,
            "source_account_id": bank if kind == "EXPENSE" else None,
            "destination_account_id": bank if kind == "INCOME" else None,
        })
        assert result.status_code == 201, result.text

    movement("INCOME", "50.00")
    movement("EXPENSE", "20.00", rent)
    movement("EXPENSE", "10.00", food)
    movement("EXPENSE", "5.00", food, "PENDING")
    housing_budget = client.post("/api/v1/budgets", headers=auth, json={
        "category_id": housing, "period": "MONTH", "currency": "EUR", "amount": "25.00",
    })
    assert housing_budget.status_code == 201, housing_budget.text
    all_budget = client.post("/api/v1/budgets", headers=auth, json={
        "period": "MONTH", "currency": "EUR", "amount": "40.00",
    })
    assert all_budget.status_code == 201, all_budget.text
    assert client.post("/api/v1/budgets", headers=auth, json={
        "category_id": housing, "period": "MONTH", "currency": "EUR", "amount": "35.00",
    }).status_code == 409
    statuses = client.get("/api/v1/budget-status", headers=auth).json()
    assert statuses[0]["spent"] == "20.00"
    assert statuses[0]["remaining"] == "5.00"
    assert statuses[1]["spent"] == "30.00"
    stats = client.get("/api/v1/statistics?period=MONTH", headers=auth).json()
    assert stats["income_by_currency"]["EUR"] == "50.00"
    assert stats["expense_by_currency"]["EUR"] == "30.00"
    assert {item["name"] for item in stats["expenses_by_category"]} == {"Vivienda / Alquiler", "Comida"}
    assert client.get("/api/v1/statistics?period=SALARY_CYCLE", headers=auth).status_code == 422
    source = client.post("/api/v1/income-sources", headers=auth, json={
        "name": "Nómina", "amount": "50.00", "account_id": bank, "day_rule": "FIXED_DAY",
        "day_of_month": today.day, "starts_on": date(today.year - 1, 1, 1).isoformat(), "is_primary": True,
    })
    assert source.status_code == 201, source.text
    cycle_budget = client.post("/api/v1/budgets", headers=auth, json={
        "period": "SALARY_CYCLE", "currency": "EUR", "amount": "100.00",
    })
    assert cycle_budget.status_code == 201, cycle_budget.text
    statuses = client.get("/api/v1/budget-status", headers=auth).json()
    assert statuses[-1]["spent"] == "30.00"
    assert client.get("/api/v1/statistics?period=SALARY_CYCLE", headers=auth).status_code == 200


def test_budget_isolation(client, auth):
    mine = client.post("/api/v1/budgets", headers=auth, json={
        "period": "MONTH", "currency": "EUR", "amount": "50.00",
    }).json()["id"]
    other = client.post("/api/v1/auth/register", json={"email": "budgets-other@example.com", "password": "another-strong-password"})
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get("/api/v1/budgets", headers=other_auth).json() == []
    assert client.patch(f"/api/v1/budgets/{mine}", headers=other_auth, json={"amount": "1.00"}).status_code == 404
