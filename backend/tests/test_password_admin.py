from app.core.config import settings


def test_user_can_change_password_and_old_sessions_stop_working(client, auth):
    endpoint = "/api/v1/auth/change-password"
    assert client.post(endpoint, headers=auth, json={
        "current_password": "incorrect", "new_password": "new-strong-password",
    }).status_code == 400
    assert client.post(endpoint, headers=auth, json={
        "current_password": "a-strong-password", "new_password": "short",
    }).status_code == 422
    changed = client.post(endpoint, headers=auth, json={
        "current_password": "a-strong-password", "new_password": "new-strong-password",
    })
    assert changed.status_code == 200, changed.text
    assert changed.headers["cache-control"] == "no-store"
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401
    new_auth = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=new_auth).status_code == 200
    assert client.post("/api/v1/auth/login", json={
        "email": "uno@example.com", "password": "a-strong-password",
    }).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "email": "uno@example.com", "password": "new-strong-password",
    }).status_code == 200


def test_admin_creates_users_and_resets_passwords_with_registration_closed(client, auth, monkeypatch):
    gateway = {"X-SpiderFinance-Admin-Gateway": "local"}
    monkeypatch.setattr(settings, "superuser_email", "")
    monkeypatch.setattr(settings, "superuser_password", "")
    assert client.post("/api/v1/admin/login", json={
        "email": "admin@example.com", "password": "admin-password-long-enough",
    }).status_code == 404
    assert client.post("/api/v1/admin/login", headers=gateway, json={
        "email": "admin@example.com", "password": "admin-password-long-enough",
    }).status_code == 503
    monkeypatch.setattr(settings, "superuser_email", "admin@example.com")
    monkeypatch.setattr(settings, "superuser_password", "admin-password-long-enough")
    monkeypatch.setattr(settings, "registration_enabled", False)

    assert client.post("/api/v1/admin/login", json={
        "email": "admin@example.com", "password": "wrong",
    }).status_code == 404
    assert client.post("/api/v1/admin/login", headers=gateway, json={
        "email": "admin@example.com", "password": "wrong",
    }).status_code == 401
    logged_in = client.post("/api/v1/admin/login", json={
        "email": "admin@example.com", "password": "admin-password-long-enough",
    }, headers=gateway)
    assert logged_in.status_code == 200
    assert logged_in.headers["cache-control"] == "no-store"
    admin_auth = {**gateway, "Authorization": f"Bearer {logged_in.json()['access_token']}"}
    assert client.get("/api/v1/admin/users", headers=auth).status_code == 404
    assert client.get("/api/v1/admin/users", headers={**gateway, **auth}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=admin_auth).status_code == 401
    assert client.get("/api/v1/admin/users", headers=admin_auth).status_code == 200

    created = client.post("/api/v1/admin/users", headers=admin_auth, json={"email": "NEW@example.com"})
    assert created.status_code == 201, created.text
    assert created.headers["cache-control"] == "no-store"
    user = created.json()["user"]
    password = created.json()["password"]
    assert user["email"] == "new@example.com"
    assert len(password) == 12 and password.isalnum()
    assert client.post("/api/v1/admin/users", headers=admin_auth, json={"email": "new@example.com"}).status_code == 409
    user_login = client.post("/api/v1/auth/login", json={"email": user["email"], "password": password})
    assert user_login.status_code == 200
    user_auth = {"Authorization": f"Bearer {user_login.json()['access_token']}"}
    assert client.get("/api/v1/categories", headers=user_auth).json()

    reset = client.post(f"/api/v1/admin/users/{user['id']}/reset-password", headers=admin_auth)
    assert reset.status_code == 200, reset.text
    new_password = reset.json()["password"]
    assert len(new_password) == 12 and new_password.isalnum() and new_password != password
    assert reset.headers["cache-control"] == "no-store"
    assert client.get("/api/v1/auth/me", headers=user_auth).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": user["email"], "password": password}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": user["email"], "password": new_password}).status_code == 200
    assert client.post("/api/v1/admin/users/999/reset-password", headers=admin_auth).status_code == 404

    monkeypatch.setattr(settings, "superuser_password", "different-admin-password")
    assert client.get("/api/v1/admin/users", headers=admin_auth).status_code == 401
