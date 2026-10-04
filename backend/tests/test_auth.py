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


def test_color_theme_is_saved_per_user(client, auth):
    assert client.get("/api/v1/settings", headers=auth).json()["theme"] == "light-teal"
    for theme in ("light-red", "dark-red", "dark-purple", "light-teal"):
        response = client.patch("/api/v1/settings", headers=auth, json={"theme": theme})
        assert response.status_code == 200, response.text
        assert response.json()["theme"] == theme
        assert client.get("/api/v1/settings", headers=auth).json()["theme"] == theme
    assert client.patch("/api/v1/settings", headers=auth, json={"theme": "unknown"}).status_code == 422
    assert client.patch("/api/v1/settings", headers=auth, json={"theme": None}).status_code == 422

    other = client.post("/api/v1/auth/register", json={
        "email": "another-theme@example.com", "password": "another-strong-password",
    })
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get("/api/v1/settings", headers=other_auth).json()["theme"] == "light-teal"
    assert client.patch("/api/v1/settings", headers=auth, json={"theme": "dark-purple"}).status_code == 200
    assert client.get("/api/v1/settings", headers=other_auth).json()["theme"] == "light-teal"
