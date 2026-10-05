"""Authentication and database dependencies shared by HTTP adapters."""

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_admin_token, decode_token
from app.modules.identity.domain import Principal
from app.modules.identity.infrastructure import SqlIdentityStore

DbSession = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def current_user(
    db: DbSession, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> Principal:
    if credentials is None:
        raise HTTPException(401, "Autenticación necesaria", headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id, auth_version = decode_token(credentials.credentials)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Sesión inválida", headers={"WWW-Authenticate": "Bearer"}) from None
    user = SqlIdentityStore(db).user(user_id)
    if user is None or user["auth_version"] != auth_version:
        raise HTTPException(401, "Sesión inválida")
    return Principal(id=user_id, auth_version=auth_version)


CurrentUser = Annotated[Principal, Depends(current_user)]


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
