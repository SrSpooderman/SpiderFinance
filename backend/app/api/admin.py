import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import AdminAuth, DbSession, require_local_gateway
from app.api.schemas import AdminCreateUserIn, AdminPasswordOut, LoginIn, TokenOut, UserOut
from app.application.users import create_user
from app.core.config import settings
from app.core.security import create_admin_token, hash_password, verify_password
from app.infrastructure.models import User

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_local_gateway)])
PASSWORD_ALPHABET = string.ascii_letters + string.digits


def temporary_password() -> str:
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(12))


@router.post("/login", response_model=TokenOut)
def admin_login(data: LoginIn, response: Response) -> TokenOut:
    if not settings.superuser_email or len(settings.superuser_password) < 12:
        raise HTTPException(503, "Administración no configurada")
    email_matches = secrets.compare_digest(str(data.email).lower().encode(), settings.superuser_email.strip().lower().encode())
    password_matches = secrets.compare_digest(data.password.encode(), settings.superuser_password.encode())
    if not email_matches or not password_matches:
        raise HTTPException(401, "Credenciales incorrectas")
    response.headers["Cache-Control"] = "no-store"
    return TokenOut(access_token=create_admin_token())


@router.get("/users", response_model=list[UserOut])
def list_users(_admin: AdminAuth, db: DbSession, response: Response) -> list[User]:
    response.headers["Cache-Control"] = "no-store"
    return list(db.scalars(select(User).order_by(User.id)).all())


@router.post("/users", response_model=AdminPasswordOut, status_code=201)
def admin_create_user(data: AdminCreateUserIn, _admin: AdminAuth, db: DbSession, response: Response) -> AdminPasswordOut:
    password = temporary_password()
    try:
        user = create_user(db, str(data.email), password)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe una cuenta con este correo") from None
    response.headers["Cache-Control"] = "no-store"
    return AdminPasswordOut(user=UserOut.model_validate(user), password=password)


@router.post("/users/{user_id}/reset-password", response_model=AdminPasswordOut)
def admin_reset_password(user_id: int, _admin: AdminAuth, db: DbSession, response: Response) -> AdminPasswordOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Usuario no encontrado")
    password = temporary_password()
    while verify_password(password, user.password_hash):
        password = temporary_password()
    user.password_hash = hash_password(password)
    user.auth_version += 1
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return AdminPasswordOut(user=UserOut.model_validate(user), password=password)
