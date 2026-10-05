import secrets

from fastapi import APIRouter, Depends, HTTPException, Response

from app.http.dependencies import AdminAuth, DbSession, require_local_gateway
from app.modules.identity.schemas import AdminCreateUserIn, AdminPasswordOut, LoginIn, TokenOut, UserOut
from app.core.config import settings
from app.core.security import create_admin_token
from app.modules.identity.application import Identity
from app.modules.identity.infrastructure import CoreCredentials, SqlIdentityStore

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_local_gateway)])


def identity(db: DbSession) -> Identity:
    return Identity(SqlIdentityStore(db), CoreCredentials())


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


@router.post("/users", response_model=AdminPasswordOut, status_code=201)
def admin_create_user(data: AdminCreateUserIn, _admin: AdminAuth, db: DbSession, response: Response):
    result = identity(db).admin_create_user(str(data.email))
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/users/{user_id}/reset-password", response_model=AdminPasswordOut)
def admin_reset_password(user_id: int, _admin: AdminAuth, db: DbSession, response: Response):
    result = identity(db).admin_reset_password(user_id)
    response.headers["Cache-Control"] = "no-store"
    return result
