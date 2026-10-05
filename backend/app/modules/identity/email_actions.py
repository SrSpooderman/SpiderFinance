"""Email ownership, invitations and password recovery use cases."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

from app.modules.errors import UseCaseError
from app.modules.identity.ports import AccountEmailConfig, Credentials, IdentityActionStore
from app.modules.notifications.ports import MailConfigurationError, MailDeliveryError, MailMessage, MailSender


class AccountEmails:
    def __init__(self, store: IdentityActionStore, credentials: Credentials, sender: MailSender, config: AccountEmailConfig):
        self.store = store
        self.credentials = credentials
        self.sender = sender
        self.config = config

    def _base_url(self) -> str:
        if not self.config.smtp_enabled:
            raise UseCaseError(503, "El correo electrónico no está activado")
        if not self.config.smtp_host or not self.config.smtp_from or bool(self.config.smtp_username) != bool(self.config.smtp_password.get_secret_value()):
            raise UseCaseError(503, "La configuración SMTP está incompleta")
        url = self.config.app_public_url.rstrip("/")
        parsed = urlparse(url)
        if not parsed.hostname or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password or (
            parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"})
        ):
            raise UseCaseError(503, "Configura APP_PUBLIC_URL con la dirección pública HTTPS de SpiderFinance")
        return url

    def _issue(self, user: dict, purpose: str, *, throttle: bool = True, deferred: bool = False) -> MailMessage | None:
        base_url = self._base_url()
        email = user["email"].lower()
        if throttle:
            key = hmac.new(self.config.secret_key.encode(), f"{purpose}:{email}".encode(), hashlib.sha256).hexdigest()
            if not self.store.allow_mail(key):
                return None
        raw = secrets.token_urlsafe(32)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        ttl = timedelta(hours=24) if purpose in {"verify", "invite"} else timedelta(minutes=30)
        self.store.issue_action(user["id"], purpose, digest, datetime.now(timezone.utc) + ttl)
        route = "/verify-email" if purpose == "verify" else "/reset-password"
        # Fragment identifiers are handled by the browser and never reach HTTP access logs.
        link = f"{base_url}{route}#{urlencode({'token': raw, 'kind': purpose})}"
        subject = {"verify": "Verifica tu correo en SpiderFinance", "invite": "Tu invitación a SpiderFinance", "reset": "Recupera tu contraseña de SpiderFinance"}[purpose]
        action = {"verify": "verificar tu correo", "invite": "crear tu contraseña y activar tu cuenta", "reset": "elegir una contraseña nueva"}[purpose]
        message = MailMessage(email, subject, f"Abre este enlace para {action}:\n\n{link}\n\nSi no has solicitado este mensaje, puedes ignorarlo. El enlace caduca en {'24 horas' if purpose != 'reset' else '30 minutos'}.")
        if not deferred:
            self.sender.send(message)
        return message

    def verify_request(self, user_id: int) -> None:
        user = self.store.user(user_id)
        if user is None:
            raise UseCaseError(404, "Usuario no encontrado")
        if user["email_verified_at"] is None:
            self._issue(user, "verify")

    def verify(self, token: str) -> None:
        self.store.finish_action(hashlib.sha256(token.encode()).hexdigest(), "verify")

    def request_reset(self, email: str) -> MailMessage | None:
        self._base_url()
        normalized = email.lower()
        key = hmac.new(self.config.secret_key.encode(), f"reset:{normalized}".encode(), hashlib.sha256).hexdigest()
        if not self.store.allow_mail(key):
            return None
        user = self.store.user_by_email(normalized)
        if user is not None and user["email_verified_at"] is not None:
            return self._issue(user, "reset", throttle=False, deferred=True)
        return None

    def complete_password(self, token: str, purpose: str, password: str) -> None:
        if purpose not in {"reset", "invite"}:
            raise UseCaseError(400, "El enlace no es válido")
        user = self.store.finish_action(hashlib.sha256(token.encode()).hexdigest(), purpose, self.credentials.hash(password))
        try:
            self.sender.send(MailMessage(user["email"], "Contraseña actualizada en SpiderFinance", "La contraseña de tu cuenta se ha actualizado. Si no has sido tú, ponte en contacto con el administrador de tu servidor."))
        except (MailConfigurationError, MailDeliveryError):
            # The committed password change must remain valid even if the notice fails.
            pass

    def admin_invite(self, email: str) -> tuple[dict, bool]:
        self._base_url()
        if self.store.user_by_email(email.lower()):
            raise UseCaseError(409, "Ya existe una cuenta con este correo")
        # A random password is never returned or mailed; only the invitation can set it.
        user = self.store.create_user(email.lower(), self.credentials.hash(secrets.token_urlsafe(48)))
        try:
            self._issue(user, "invite", throttle=False)
            return user, True
        except (MailConfigurationError, MailDeliveryError):
            return user, False

    def admin_recovery(self, user_id: int) -> str:
        self._base_url()
        user = self.store.user(user_id)
        if user is None:
            raise UseCaseError(404, "Usuario no encontrado")
        purpose = "reset" if user["email_verified_at"] is not None else "invite"
        if self._issue(user, purpose) is None:
            raise UseCaseError(429, "Espera un minuto antes de reenviar el correo")
        return "recovery_sent" if purpose == "reset" else "invitation_sent"
