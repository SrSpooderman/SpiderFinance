import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.db import get_db
from app.infrastructure.models import IdentityActionToken, IdentityMailThrottle
from app.main import app
from app.modules.notifications.infrastructure import MailDeliveryError, SmtpMailSender


def token_from(messages):
    return re.search(r"token=([^&\s]+)", messages[-1].text).group(1)


def enable_mail(monkeypatch):
    messages = []
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "app_public_url", "https://finance.example.test")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_from", "no-reply@example.test")
    monkeypatch.setattr(SmtpMailSender, "send", lambda self, message: messages.append(message))
    return messages


def admin_headers(client, monkeypatch):
    monkeypatch.setattr(settings, "superuser_email", "admin@example.com")
    monkeypatch.setattr(settings, "superuser_password", "admin-password-long-enough")
    gateway = {"X-SpiderFinance-Admin-Gateway": "local"}
    logged = client.post("/api/v1/admin/login", headers=gateway, json={"email": "admin@example.com", "password": "admin-password-long-enough"})
    assert logged.status_code == 200
    return {**gateway, "Authorization": f"Bearer {logged.json()['access_token']}"}


def db_session():
    return next(app.dependency_overrides[get_db]())


def test_change_password_revokes_sessions(client, auth):
    endpoint = "/api/v1/auth/change-password"
    assert client.post(endpoint, headers=auth, json={"current_password": "wrong", "new_password": "new-strong-password"}).status_code == 400
    assert client.post(endpoint, headers=auth, json={"current_password": "a-strong-password", "new_password": "new-strong-password"}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "uno@example.com", "password": "a-strong-password"}).status_code == 401


def test_verified_user_can_recover_with_one_time_link(client, auth, monkeypatch):
    messages = enable_mail(monkeypatch)
    request = "/api/v1/auth/password-recovery/request"
    unknown = client.post(request, json={"email": "nobody@example.com"})
    unverified = client.post(request, json={"email": "uno@example.com"})
    assert unknown.status_code == unverified.status_code == 202
    assert unknown.json() == unverified.json()
    assert messages == []
    assert client.post("/api/v1/auth/email-verification/request", headers=auth).status_code == 202
    verification = token_from(messages)
    assert client.post("/api/v1/auth/email-verification/complete", json={"token": verification}).status_code == 200
    assert client.post("/api/v1/auth/email-verification/complete", json={"token": verification}).status_code == 400
    assert client.get("/api/v1/auth/me", headers=auth).json()["email_verified_at"]
    db = db_session()
    for item in db.scalars(select(IdentityMailThrottle)):
        item.last_requested_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    db.commit()
    db.close()
    assert client.post(request, json={"email": "uno@example.com"}).status_code == 202
    reset = token_from(messages)
    assert client.post("/api/v1/auth/login", json={"email": "uno@example.com", "password": "a-strong-password"}).status_code == 200
    completed = client.post("/api/v1/auth/password-recovery/complete", json={"token": reset, "kind": "reset", "new_password": "new-strong-password"})
    assert completed.status_code == 200, completed.text
    assert client.post("/api/v1/auth/password-recovery/complete", json={"token": reset, "kind": "reset", "new_password": "another-strong-password"}).status_code == 400
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "uno@example.com", "password": "a-strong-password"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "uno@example.com", "password": "new-strong-password"}).status_code == 200


def test_admin_invitation_and_recovery_never_reveal_secrets(client, auth, monkeypatch):
    headers = admin_headers(client, monkeypatch)
    monkeypatch.setattr(settings, "registration_enabled", False)
    assert client.post("/api/v1/admin/users", headers=headers, json={"email": "new@example.com"}).status_code == 503
    messages = enable_mail(monkeypatch)
    created = client.post("/api/v1/admin/users", headers=headers, json={"email": "NEW@example.com"})
    assert created.status_code == 201, created.text
    assert "password" not in created.text and "token" not in created.text
    user = created.json()["user"]
    assert user["email"] == "new@example.com"
    invitation = token_from(messages)
    assert client.post("/api/v1/auth/password-recovery/complete", json={"token": invitation, "kind": "invite", "new_password": "invite-password-long"}).status_code == 200
    logged = client.post("/api/v1/auth/login", json={"email": user["email"], "password": "invite-password-long"})
    assert logged.status_code == 200
    user_auth = {"Authorization": f"Bearer {logged.json()['access_token']}"}
    requested = client.post(f"/api/v1/admin/users/{user['id']}/password-recovery", headers=headers)
    assert requested.status_code == 202
    assert "password" not in requested.text and "token" not in requested.text
    assert client.get("/api/v1/auth/me", headers=user_auth).status_code == 200
    assert client.post(f"/api/v1/admin/users/{user['id']}/reset-password", headers=headers).status_code == 404


def test_expired_token_and_mail_disabled(client, auth, monkeypatch):
    messages = enable_mail(monkeypatch)
    client.post("/api/v1/auth/email-verification/request", headers=auth)
    token = token_from(messages)
    db = db_session()
    db.scalar(select(IdentityActionToken)).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    db.close()
    assert client.post("/api/v1/auth/email-verification/complete", json={"token": token}).status_code == 400
    monkeypatch.setattr(settings, "smtp_enabled", False)
    assert client.post("/api/v1/auth/email-verification/request", headers=auth).status_code == 503
    assert client.post("/api/v1/auth/password-recovery/request", json={"email": "uno@example.com"}).status_code == 503


def test_registration_sends_verification_and_new_link_replaces_old(client, monkeypatch):
    messages = enable_mail(monkeypatch)
    registered = client.post("/api/v1/auth/register", json={"email": "first@example.com", "password": "a-strong-password"})
    assert registered.status_code == 201
    auth = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    assert len(messages) == 1
    first = token_from(messages)
    assert "#token=" in messages[0].text
    db = db_session()
    for item in db.scalars(select(IdentityMailThrottle)):
        item.last_requested_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    db.commit()
    db.close()
    assert client.post("/api/v1/auth/email-verification/request", headers=auth).status_code == 202
    second = token_from(messages)
    assert first != second
    assert client.post("/api/v1/auth/email-verification/complete", json={"token": first}).status_code == 400
    assert client.post("/api/v1/auth/email-verification/complete", json={"token": second}).status_code == 200


def test_failed_invitation_can_be_resent_and_request_does_not_change_password(client, monkeypatch):
    headers = admin_headers(client, monkeypatch)
    messages = enable_mail(monkeypatch)
    def fail(self, message):
        raise MailDeliveryError("SMTP indisponible")
    monkeypatch.setattr(SmtpMailSender, "send", fail)
    created = client.post("/api/v1/admin/users", headers=headers, json={"email": "pending@example.com"})
    assert created.status_code == 201
    assert "no se pudo enviar" in created.json()["message"]
    user_id = created.json()["user"]["id"]
    monkeypatch.setattr(SmtpMailSender, "send", lambda self, message: messages.append(message))
    resent = client.post(f"/api/v1/admin/users/{user_id}/password-recovery", headers=headers)
    assert resent.status_code == 202
    assert messages
    assert client.post("/api/v1/auth/login", json={"email": "pending@example.com", "password": "a-strong-password"}).status_code == 401
    invitation = token_from(messages)
    assert client.post("/api/v1/auth/password-recovery/complete", json={"token": invitation, "kind": "invite", "new_password": "new-strong-password"}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "pending@example.com", "password": "new-strong-password"}).status_code == 200


def test_changing_password_invalidates_pending_recovery_links(client, auth, monkeypatch):
    messages = enable_mail(monkeypatch)
    client.post("/api/v1/auth/email-verification/request", headers=auth)
    client.post("/api/v1/auth/email-verification/complete", json={"token": token_from(messages)})
    client.post("/api/v1/auth/password-recovery/request", json={"email": "uno@example.com"})
    pending = token_from(messages)
    changed = client.post("/api/v1/auth/change-password", headers=auth, json={
        "current_password": "a-strong-password", "new_password": "new-strong-password",
    })
    assert changed.status_code == 200
    assert client.post("/api/v1/auth/password-recovery/complete", json={
        "token": pending, "kind": "reset", "new_password": "attacker-password-long",
    }).status_code == 400
