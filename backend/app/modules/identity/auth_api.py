from fastapi import APIRouter, BackgroundTasks, File, Response, UploadFile

from app.http.dependencies import CurrentUser, DbSession
from app.modules.identity.schemas import ActionTokenIn, CompletePasswordIn, EmailIn, LoginIn, MessageOut, PasswordChangeIn, ProfilePhotoOut, RegisterIn, SettingsOut, SettingsPatch, TokenOut, UserOut
from app.core.config import settings
from app.modules.identity.application import Identity
from app.modules.identity.domain import MAX_PROFILE_PHOTO_BYTES
from app.modules.identity.infrastructure import CoreCredentials, SqlIdentityStore
from app.modules.identity.email_actions import AccountEmails
from app.modules.notifications.infrastructure import SmtpMailSender
from app.modules.notifications.infrastructure import MailConfigurationError, MailDeliveryError
from app.modules.errors import UseCaseError
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


def identity(db: DbSession) -> Identity:
    return Identity(SqlIdentityStore(db), CoreCredentials())


def account_emails(db: DbSession) -> AccountEmails:
    return AccountEmails(SqlIdentityStore(db), CoreCredentials(), SmtpMailSender(), settings)


@router.get("/auth/config")
def auth_config() -> dict[str, bool]:
    return {"registration_enabled": settings.registration_enabled, "email_enabled": settings.smtp_enabled and bool(settings.app_public_url and settings.smtp_host and settings.smtp_from)}


@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: DbSession):
    result = identity(db).register(str(data.email), data.password, settings.registration_enabled)
    if settings.smtp_enabled:
        try:
            from app.core.security import decode_token
            user_id, _ = decode_token(result["access_token"])
            account_emails(db).verify_request(user_id)
        except (MailConfigurationError, MailDeliveryError, UseCaseError):
            logger.exception("Unable to send registration verification email")
    return result


@router.post("/auth/email-verification/request", response_model=MessageOut, status_code=202)
def request_verification(user: CurrentUser, db: DbSession, response: Response):
    account_emails(db).verify_request(user.id)
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Si está pendiente, recibirás un correo de verificación"}


@router.post("/auth/email-verification/complete", response_model=MessageOut)
def complete_verification(data: ActionTokenIn, db: DbSession, response: Response):
    account_emails(db).verify(data.token)
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Correo verificado"}


@router.post("/auth/password-recovery/request", response_model=MessageOut, status_code=202)
def request_password_recovery(data: EmailIn, db: DbSession, response: Response, background_tasks: BackgroundTasks):
    message = account_emails(db).request_reset(str(data.email))
    if message is not None:
        background_tasks.add_task(send_recovery_mail, message)
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Si la cuenta puede recuperarse, recibirás un correo con instrucciones"}


def send_recovery_mail(message) -> None:
    try:
        SmtpMailSender().send(message)
    except (MailConfigurationError, MailDeliveryError):
        logger.exception("Unable to send password recovery email")


@router.post("/auth/password-recovery/complete", response_model=MessageOut)
def complete_password_recovery(data: CompletePasswordIn, db: DbSession, response: Response):
    account_emails(db).complete_password(data.token, data.kind, data.new_password)
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Contraseña actualizada. Inicia sesión de nuevo"}


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: DbSession):
    return identity(db).login(str(data.email), data.password)


@router.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser, db: DbSession):
    return identity(db).user(user.id)


@router.post("/auth/change-password", response_model=TokenOut)
def change_password(data: PasswordChangeIn, user: CurrentUser, db: DbSession, response: Response):
    result = identity(db).change_password(user.id, data.current_password, data.new_password)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/auth/profile-photo", response_model=ProfilePhotoOut)
def get_profile_photo(user: CurrentUser, db: DbSession, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return identity(db).photo(user.id)


@router.put("/auth/profile-photo", response_model=ProfilePhotoOut)
async def put_profile_photo(user: CurrentUser, db: DbSession, photo: UploadFile = File(...)):
    data = await photo.read(MAX_PROFILE_PHOTO_BYTES + 1)
    return identity(db).save_photo(user.id, data)


@router.delete("/auth/profile-photo", status_code=204)
def delete_profile_photo(user: CurrentUser, db: DbSession) -> None:
    identity(db).delete_photo(user.id)


@router.get("/settings", response_model=SettingsOut, tags=["settings"])
def get_settings(user: CurrentUser, db: DbSession):
    return identity(db).settings(user.id)


@router.patch("/settings", response_model=SettingsOut, tags=["settings"])
def update_settings(data: SettingsPatch, user: CurrentUser, db: DbSession):
    return identity(db).update_settings(user.id, data.model_dump(exclude_unset=True))
