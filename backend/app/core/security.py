from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import new as hmac_new
from secrets import compare_digest

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

from app.core.config import settings

hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, stored: str) -> bool:
    try:
        return hasher.verify(stored, password)
    except (VerifyMismatchError, VerificationError):
        return False


def create_token(user_id: int, auth_version: int = 0) -> str:
    expiry = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "kind": "user", "ver": auth_version, "exp": expiry}, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> tuple[int, int]:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if payload.get("kind", "user") != "user":
        raise ValueError("Tipo de sesión inválido")
    return int(payload["sub"]), int(payload.get("ver", 0))


def _admin_credential_version() -> str:
    credential = f"{settings.superuser_email.lower()}\0{settings.superuser_password}".encode()
    return hmac_new(settings.secret_key.encode(), credential, sha256).hexdigest()


def create_admin_token() -> str:
    expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
    return jwt.encode({"sub": "superuser", "kind": "admin", "cred": _admin_credential_version(), "exp": expiry}, settings.secret_key, algorithm="HS256")


def decode_admin_token(token: str) -> None:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if payload.get("kind") != "admin" or payload.get("sub") != "superuser":
        raise ValueError("Tipo de sesión inválido")
    if not settings.superuser_email or not settings.superuser_password:
        raise ValueError("Administración desactivada")
    if not compare_digest(str(payload.get("cred", "")), _admin_credential_version()):
        raise ValueError("Sesión administrativa caducada")
