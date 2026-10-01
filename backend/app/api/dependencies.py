from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.infrastructure.models import User

DbSession = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def current_user(
    db: DbSession, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> User:
    if credentials is None:
        raise HTTPException(401, "Autenticación necesaria", headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id = decode_token(credentials.credentials)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Sesión inválida", headers={"WWW-Authenticate": "Bearer"}) from None
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(401, "Sesión inválida")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
