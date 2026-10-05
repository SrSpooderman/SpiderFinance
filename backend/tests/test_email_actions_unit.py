from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.modules.errors import UseCaseError
from app.modules.identity.email_actions import AccountEmails


class FakeStore:
    def __init__(self):
        self.accounts = {}
        self.issued = []
        self.allowed = True

    def user_by_email(self, email):
        return self.accounts.get(email)

    def user(self, user_id):
        return next((user for user in self.accounts.values() if user["id"] == user_id), None)

    def create_user(self, email, password_hash):
        user = {"id": len(self.accounts) + 1, "email": email, "password_hash": password_hash, "email_verified_at": None}
        self.accounts[email] = user
        return user

    def allow_mail(self, key):
        return self.allowed

    def issue_action(self, user_id, purpose, token_hash, expires_at):
        self.issued.append((user_id, purpose, token_hash, expires_at))


class FakeCredentials:
    def hash(self, password):
        return f"hashed:{password}"


class FakeSender:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


def service(url="https://finance.example.test"):
    store = FakeStore()
    sender = FakeSender()
    config = SimpleNamespace(smtp_enabled=True, smtp_host="smtp.example.test", smtp_from="no-reply@example.test", smtp_username="", smtp_password=SecretStr(""), app_public_url=url, secret_key="x" * 32)
    return AccountEmails(store, FakeCredentials(), sender, config), store, sender


def test_invitation_stores_only_hash_and_does_not_return_password_or_token():
    actions, store, sender = service()
    user, sent = actions.admin_invite("NEW@example.test")
    assert sent is True
    assert user["email"] == "new@example.test"
    assert user["password_hash"].startswith("hashed:")
    assert len(store.issued[0][2]) == 64
    assert store.issued[0][2] not in sender.messages[0].text
    assert "#token=" in sender.messages[0].text
    assert sender.messages[0].recipient == user["email"]


@pytest.mark.parametrize("url", ["http://finance.example.test", "https://finance.example.test/other", "https://user:pass@finance.example.test", "javascript:alert(1)"])
def test_external_or_unsafe_link_base_is_rejected_before_creating_an_account(url):
    actions, store, sender = service(url)
    with pytest.raises(UseCaseError) as error:
        actions.admin_invite("new@example.test")
    assert error.value.status == 503
    assert store.accounts == {}
    assert sender.messages == []


def test_unverified_account_has_no_self_service_recovery_message():
    actions, store, sender = service()
    store.create_user("new@example.test", "hash")
    assert actions.request_reset("new@example.test") is None
    assert actions.request_reset("absent@example.test") is None
    assert sender.messages == []
    assert store.issued == []
