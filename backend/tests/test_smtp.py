"""SMTP transport tests without an external mail server."""

from email.message import EmailMessage

import pytest

from app.core.config import Settings
from app.modules.notifications.infrastructure import (
    MailConfigurationError, MailDeliveryError, SmtpMailSender,
)
from app.modules.notifications.ports import MailMessage


class FakeSMTP:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.events.append(("close",))

    def starttls(self, *, context):
        self.events.append(("starttls", bool(context)))

    def login(self, username, password):
        self.events.append(("login", username, password))

    def send_message(self, message, *, from_addr, to_addrs):
        self.events.append(("send", message, from_addr, to_addrs))


def config(**changes):
    return Settings(_env_file=None, smtp_enabled=True, smtp_host="smtp.example.com",
                    smtp_from="sender@example.com", **changes)


def message(**changes):
    return MailMessage(recipient="user@example.com", subject="Aviso", text="Hola", **changes)


def test_starttls_authenticates_only_after_upgrading_connection(monkeypatch):
    events = []
    monkeypatch.setattr("app.modules.notifications.infrastructure.smtplib.SMTP",
                        lambda host, port, **kwargs: events.append(("connect", host, port)) or FakeSMTP(events))

    SmtpMailSender(config(smtp_username="mailer", smtp_password="test-secret")).send(message(html="<p>Hola</p>"))

    assert [event[0] for event in events] == ["connect", "starttls", "login", "send", "close"]
    assert events[2] == ("login", "mailer", "test-secret")
    sent: EmailMessage = events[3][1]
    assert events[3][2:] == ("sender@example.com", ["user@example.com"])
    assert sent["Subject"] == "Aviso"
    assert sent.get_body(preferencelist=("html",)).get_content() == "<p>Hola</p>\n"


def test_implicit_tls_uses_secure_socket(monkeypatch):
    events = []
    monkeypatch.setattr("app.modules.notifications.infrastructure.smtplib.SMTP_SSL",
                        lambda host, port, **kwargs: events.append(("ssl_connect", host, port, bool(kwargs["context"])))
                        or FakeSMTP(events))

    SmtpMailSender(config(smtp_port=465, smtp_security="ssl")).send(message())

    assert [event[0] for event in events] == ["ssl_connect", "send", "close"]
    assert events[0] == ("ssl_connect", "smtp.example.com", 465, True)


def test_local_smtp_without_credentials_sends_without_tls(monkeypatch):
    events = []
    monkeypatch.setattr("app.modules.notifications.infrastructure.smtplib.SMTP",
                        lambda host, port, **kwargs: FakeSMTP(events))

    SmtpMailSender(config(smtp_security="none", smtp_port=1025)).send(message())

    assert [event[0] for event in events] == ["send", "close"]


def test_plaintext_mode_rejects_authentication():
    with pytest.raises(MailConfigurationError, match="requiere STARTTLS o TLS"):
        SmtpMailSender(config(smtp_security="none", smtp_username="mailer",
                              smtp_password="test-secret")).send(message())


def test_disabled_smtp_never_opens_connection(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("No debe abrir una conexión SMTP")

    monkeypatch.setattr("app.modules.notifications.infrastructure.smtplib.SMTP", fail)
    with pytest.raises(MailConfigurationError, match="desactivado"):
        SmtpMailSender(Settings(_env_file=None, smtp_enabled=False,
                                smtp_host="smtp.example.com", smtp_from="sender@example.com")).send(message())


@pytest.mark.parametrize("changes", [
    {"smtp_host": ""}, {"smtp_from": ""}, {"smtp_username": "mailer"},
])
def test_incomplete_configuration_fails_before_network(changes):
    values = {"smtp_enabled": True, "smtp_host": "smtp.example.com",
              "smtp_from": "sender@example.com", **changes}
    with pytest.raises(MailConfigurationError):
        SmtpMailSender(Settings(_env_file=None, **values)).send(message())


def test_recipient_must_be_one_valid_address():
    with pytest.raises(MailConfigurationError, match="Dirección de correo inválida"):
        SmtpMailSender(config()).send(MailMessage("a@example.com,b@example.com", "Aviso", "Hola"))


def test_connection_error_is_reported_without_credentials(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("app.modules.notifications.infrastructure.smtplib.SMTP", fail)
    with pytest.raises(MailDeliveryError, match="No se pudo entregar") as error:
        SmtpMailSender(config(smtp_username="mailer", smtp_password="test-secret")).send(message())
    assert "test-secret" not in str(error.value)
