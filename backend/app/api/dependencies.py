from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_admin_token, decode_token
from app.infrastructure.models import User

DbSession = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def current_user(
    db: DbSession, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> User:
    if credentials is None:
        raise HTTPException(401, "Autenticación necesaria", headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id, auth_version = decode_token(credentials.credentials)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Sesión inválida", headers={"WWW-Authenticate": "Bearer"}) from None
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or user.auth_version != auth_version:
        raise HTTPException(401, "Sesión inválida")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_admin(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> None:
    if credentials is None:
        raise HTTPException(401, "Autenticación necesaria", headers={"WWW-Authenticate": "Bearer"})
    try:
        decode_admin_token(credentials.credentials)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Sesión administrativa inválida") from None


AdminAuth = Annotated[None, Depends(require_admin)]


def require_local_gateway(gateway: Annotated[str | None, Header(alias="X-SpiderFinance-Admin-Gateway")] = None) -> None:
    if gateway != "local":
        raise HTTPException(404, "Not Found")
