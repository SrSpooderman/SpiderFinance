from datetime import date, timedelta


def test_investments_net_worth_and_snapshots(client, auth):
    today = date.today().isoformat()
    checking = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Corriente", "type": "CHECKING", "initial_balance": "1000.00", "currency": "EUR",
    }).json()["id"]
    investment = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Broker", "type": "INVESTMENT", "initial_balance": "0.00", "currency": "EUR",
    }).json()["id"]
    transfer = client.post("/api/v1/transactions", headers=auth, json={
        "date": today, "type": "TRANSFER", "concept": "Aportación al broker",
        "amount": "300.00", "source_account_id": checking, "destination_account_id": investment,
    })
    assert transfer.status_code == 201, transfer.text
    transaction_id = transfer.json()["id"]
    linked = client.post("/api/v1/investments/contributions", headers=auth, json={
        "transaction_id": transaction_id,
    })
    assert linked.status_code == 201, linked.text
    assert client.delete(f"/api/v1/transactions/{transaction_id}", headers=auth).status_code == 409
    assert client.post("/api/v1/investments/positions", headers=auth, json={
        "account_id": investment, "name": "Demasiado", "units": "1", "cost_basis": "400.00",
        "market_value": "400.00", "valued_on": today,
    }).status_code == 422
    position = client.post("/api/v1/investments/positions", headers=auth, json={
        "account_id": investment, "name": "ETF global", "symbol": "WORLD",
        "units": "2.00000000", "cost_basis": "200.00", "market_value": "250.00", "valued_on": today,
    })
    assert position.status_code == 201, position.text
    assert client.patch(f"/api/v1/investments/positions/{position.json()['id']}", headers=auth, json={
        "valued_on": (date.today() + timedelta(days=1)).isoformat(),
    }).status_code == 422
    debt = client.post("/api/v1/debts", headers=auth, json={
        "name": "Préstamo", "principal": "100.00", "installment_amount": "10.00",
        "account_id": checking, "starts_on": today, "due_day": date.today().day,
    })
    assert debt.status_code == 201, debt.text
    report = client.get("/api/v1/net-worth", headers=auth)
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["currencies"][0]["assets"] == "1050.00"
    assert data["currencies"][0]["liabilities"] == "100.00"
    assert data["currencies"][0]["net_worth"] == "950.00"
    broker = next(item for item in data["accounts"] if item["id"] == investment)
    assert broker["uninvested_cash"] == "100.00"
    assert broker["position_value"] == "250.00"
    snapshot = client.post("/api/v1/net-worth/snapshots", headers=auth)
    assert snapshot.status_code == 201, snapshot.text
    assert snapshot.json()[0]["net_worth"] == "950.00"
    assert client.post("/api/v1/net-worth/snapshots", headers=auth).status_code == 409
    assert len(client.get("/api/v1/net-worth/snapshots", headers=auth).json()) == 1
    assert client.delete(f"/api/v1/investments/contributions/{linked.json()['id']}", headers=auth).status_code == 204
    assert client.delete(f"/api/v1/transactions/{transaction_id}", headers=auth).status_code == 409


def test_investment_isolation(client, auth):
    account = client.post("/api/v1/accounts", headers=auth, json={
        "name": "Broker", "type": "INVESTMENT", "initial_balance": "20.00", "currency": "EUR",
    }).json()["id"]
    other = client.post("/api/v1/auth/register", json={"email": "investments-other@example.com", "password": "another-strong-password"})
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.post("/api/v1/investments/positions", headers=other_auth, json={
        "account_id": account, "name": "Ajena", "units": "1", "cost_basis": "10.00",
        "market_value": "10.00", "valued_on": date.today().isoformat(),
    }).status_code == 404
    assert client.get("/api/v1/net-worth", headers=other_auth).json()["accounts"] == []
