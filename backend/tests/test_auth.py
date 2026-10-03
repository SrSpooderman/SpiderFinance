from app.core.config import settings


def test_registration_can_be_closed_without_disabling_login(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "registration_enabled", False)

    config = client.get("/api/v1/auth/config")
    assert config.status_code == 200
    assert config.json() == {"registration_enabled": False}

    registration = client.post("/api/v1/auth/register", json={
        "email": "another@example.com", "password": "another-strong-password",
    })
    assert registration.status_code == 403
    assert registration.json()["detail"] == "El registro está desactivado"

    login = client.post("/api/v1/auth/login", json={
        "email": "uno@example.com", "password": "a-strong-password",
    })
    assert login.status_code == 200
    assert login.json()["access_token"]
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 200
