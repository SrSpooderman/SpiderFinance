import secrets

from fastapi import APIRouter, Depends, HTTPException, Response

from app.http.dependencies import AdminAuth, DbSession, require_local_gateway
from app.modules.identity.schemas import AdminCreateUserIn, AdminInviteOut, LoginIn, MessageOut, TokenOut, UserOut
from app.core.config import settings
from app.core.security import create_admin_token
from app.modules.identity.application import Identity
from app.modules.identity.infrastructure import CoreCredentials, SqlIdentityStore
from app.modules.identity.email_actions import AccountEmails
from app.modules.notifications.infrastructure import SmtpMailSender
from app.modules.notifications.infrastructure import MailConfigurationError, MailDeliveryError

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_local_gateway)])


def identity(db: DbSession) -> Identity:
    return Identity(SqlIdentityStore(db), CoreCredentials())


def account_emails(db: DbSession) -> AccountEmails:
    return AccountEmails(SqlIdentityStore(db), CoreCredentials(), SmtpMailSender(), settings)


@router.post("/login", response_model=TokenOut)
def admin_login(data: LoginIn, response: Response):
    if not settings.superuser_email or len(settings.superuser_password) < 12:
        raise HTTPException(503, "Administración no configurada")
    email_matches = secrets.compare_digest(str(data.email).lower().encode(), settings.superuser_email.strip().lower().encode())
    password_matches = secrets.compare_digest(data.password.encode(), settings.superuser_password.encode())
    if not email_matches or not password_matches:
        raise HTTPException(401, "Credenciales incorrectas")
    response.headers["Cache-Control"] = "no-store"
    return TokenOut(access_token=create_admin_token())


@router.get("/users", response_model=list[UserOut])
def list_users(_admin: AdminAuth, db: DbSession, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return identity(db).users()


@router.post("/users", response_model=AdminInviteOut, status_code=201)
def admin_create_user(data: AdminCreateUserIn, _admin: AdminAuth, db: DbSession, response: Response):
    user, sent = account_emails(db).admin_invite(str(data.email))
    result = {"user": user, "message": "Invitación enviada" if sent else "Cuenta creada; no se pudo enviar la invitación. Reinténtalo desde la lista de usuarios"}
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/users/{user_id}/password-recovery", response_model=MessageOut, status_code=202)
def admin_reset_password(user_id: int, _admin: AdminAuth, db: DbSession, response: Response):
    try:
        result = account_emails(db).admin_recovery(user_id)
    except (MailConfigurationError, MailDeliveryError):
        raise HTTPException(503, "No se pudo enviar el correo; inténtalo más tarde") from None
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Invitación enviada" if result == "invitation_sent" else "Recuperación enviada"}
