"""SMTP adapter. No business flow sends mail until explicitly wired to it."""

import smtplib
import ssl
from email.message import EmailMessage

from email_validator import EmailNotValidError, validate_email

from app.core.config import Settings, settings
from app.modules.notifications.ports import MailConfigurationError, MailDeliveryError, MailMessage


class SmtpMailSender:
    def __init__(self, config: Settings = settings):
        self.config = config

    def send(self, message: MailMessage) -> None:
        config = self.config
        if not config.smtp_enabled:
            raise MailConfigurationError("El envío SMTP está desactivado")
        if not config.smtp_host or not config.smtp_from:
            raise MailConfigurationError("Configura SMTP_HOST y SMTP_FROM antes de enviar correo")
        if bool(config.smtp_username) != bool(config.smtp_password.get_secret_value()):
            raise MailConfigurationError("SMTP_USERNAME y SMTP_PASSWORD deben configurarse juntos")
        if config.smtp_security == "none" and config.smtp_username:
            raise MailConfigurationError("La autenticación SMTP requiere STARTTLS o TLS")
        try:
            sender = validate_email(config.smtp_from, check_deliverability=False).normalized
            recipient = validate_email(message.recipient, check_deliverability=False).normalized
        except EmailNotValidError as exc:
            raise MailConfigurationError("Dirección de correo inválida") from exc

        email = EmailMessage()
        email["From"] = sender
        email["To"] = recipient
        email["Subject"] = message.subject
        email.set_content(message.text)
        if message.html is not None:
            email.add_alternative(message.html, subtype="html")

        try:
            if config.smtp_security == "ssl":
                connection = smtplib.SMTP_SSL(
                    config.smtp_host, config.smtp_port, timeout=config.smtp_timeout_seconds,
                    context=ssl.create_default_context(),
                )
            else:
                connection = smtplib.SMTP(
                    config.smtp_host, config.smtp_port, timeout=config.smtp_timeout_seconds,
                )
            with connection as smtp:
                if config.smtp_security == "starttls":
                    smtp.starttls(context=ssl.create_default_context())
                if config.smtp_username:
                    smtp.login(config.smtp_username, config.smtp_password.get_secret_value())
                smtp.send_message(email, from_addr=sender, to_addrs=[recipient])
        except (OSError, smtplib.SMTPException) as exc:
            raise MailDeliveryError("No se pudo entregar el correo al servidor SMTP") from exc
