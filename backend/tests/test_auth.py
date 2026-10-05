from base64 import b64decode

from app.core.config import settings


def test_registration_can_be_closed_without_disabling_login(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "registration_enabled", False)

    config = client.get("/api/v1/auth/config")
    assert config.status_code == 200
    assert config.json() == {"registration_enabled": False, "email_enabled": False}

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


def test_profile_photo_is_private_and_can_be_replaced_or_deleted(client, auth):
    image = b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lX8AAAAASUVORK5CYII=")
    assert client.get("/api/v1/auth/profile-photo", headers=auth).json() == {"data_url": None}
    for _ in range(2):
        upload = client.put("/api/v1/auth/profile-photo", headers=auth, files={"photo": ("avatar.png", image, "image/png")})
        assert upload.status_code == 200, upload.text
        assert upload.json()["data_url"].startswith("data:image/png;base64,")
    assert client.get("/api/v1/auth/profile-photo", headers=auth).json() == upload.json()

    other = client.post("/api/v1/auth/register", json={
        "email": "another-photo@example.com", "password": "another-strong-password",
    })
    other_auth = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get("/api/v1/auth/profile-photo", headers=other_auth).json() == {"data_url": None}
    assert client.get("/api/v1/auth/profile-photo").status_code == 401
    assert client.put("/api/v1/auth/profile-photo", headers=auth, files={
        "photo": ("unsafe.svg", b"<svg></svg>", "image/png"),
    }).status_code == 422
    assert client.put("/api/v1/auth/profile-photo", headers=auth, files={
        "photo": ("huge.png", b"\x89PNG\r\n\x1a\n" + b"x" * (2 * 1024 * 1024), "image/png"),
    }).status_code == 413
    assert client.delete("/api/v1/auth/profile-photo", headers=auth).status_code == 204
    assert client.get("/api/v1/auth/profile-photo", headers=auth).json() == {"data_url": None}
    assert client.get("/api/v1/auth/profile-photo", headers=other_auth).json() == {"data_url": None}
    assert client.patch("/api/v1/settings", headers=auth, json={"theme": "dark-purple"}).status_code == 200
    assert client.get("/api/v1/settings", headers=other_auth).json()["theme"] == "light-teal"
