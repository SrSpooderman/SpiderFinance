from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import LoginIn, RegisterIn, SettingsOut, SettingsPatch, TokenOut, UserOut
from app.core.config import settings
from app.core.security import create_token, hash_password, verify_password
from app.infrastructure.models import Category, User, UserSettings

router = APIRouter(tags=["auth"])

DEFAULT_CATEGORIES = (
    "Alimentación", "Restaurantes", "Transporte", "Ocio", "Ropa", "Tecnología",
    "Estudios", "Salud", "Viajes", "Hogar", "Suscripciones", "Deporte",
    "Regalos", "Mascotas", "Impuestos", "Comisiones", "Otros",
)


@router.get("/auth/config")
def auth_config() -> dict[str, bool]:
    return {"registration_enabled": settings.registration_enabled}


@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: DbSession) -> TokenOut:
    if not settings.registration_enabled:
        raise HTTPException(403, "El registro está desactivado")
    email = str(data.email).lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Ya existe una cuenta con este correo")
    user = User(email=email, password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    db.add(UserSettings(user_id=user.id))
    db.add_all(Category(user_id=user.id, name=name) for name in DEFAULT_CATEGORIES)
    db.commit()
    return TokenOut(access_token=create_token(user.id))


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: DbSession) -> TokenOut:
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Credenciales incorrectas")
    return TokenOut(access_token=create_token(user.id))


@router.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.get("/settings", response_model=SettingsOut, tags=["settings"])
def get_settings(user: CurrentUser, db: DbSession) -> UserSettings:
    return db.get(UserSettings, user.id)


@router.patch("/settings", response_model=SettingsOut, tags=["settings"])
def update_settings(data: SettingsPatch, user: CurrentUser, db: DbSession) -> UserSettings:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    settings = db.get(UserSettings, user.id)
    changes = data.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(422, "Los ajustes no pueden ser nulos")
    if "timezone" in changes:
        try:
            ZoneInfo(changes["timezone"])
        except ZoneInfoNotFoundError:
            raise HTTPException(422, "Zona horaria desconocida") from None
    for key, value in changes.items():
        setattr(settings, key, value)
    db.commit()
    return settings
