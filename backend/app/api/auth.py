from base64 import b64encode

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import LoginIn, PasswordChangeIn, ProfilePhotoOut, RegisterIn, SettingsOut, SettingsPatch, TokenOut, UserOut
from app.application.users import create_user
from app.core.config import settings
from app.core.security import create_token, hash_password, verify_password
from app.infrastructure.models import User, UserProfilePhoto, UserSettings

router = APIRouter(tags=["auth"])
MAX_PROFILE_PHOTO_BYTES = 2 * 1024 * 1024


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
    user = create_user(db, email, data.password)
    return TokenOut(access_token=create_token(user.id, user.auth_version))


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: DbSession) -> TokenOut:
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Credenciales incorrectas")
    return TokenOut(access_token=create_token(user.id, user.auth_version))


@router.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.post("/auth/change-password", response_model=TokenOut)
def change_password(data: PasswordChangeIn, user: CurrentUser, db: DbSession, response: Response) -> TokenOut:
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "La contraseña actual no es correcta")
    if data.new_password == data.current_password:
        raise HTTPException(400, "La nueva contraseña debe ser diferente")
    user.password_hash = hash_password(data.new_password)
    user.auth_version += 1
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return TokenOut(access_token=create_token(user.id, user.auth_version))


def photo_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def photo_out(photo: UserProfilePhoto | None) -> ProfilePhotoOut:
    if photo is None:
        return ProfilePhotoOut(data_url=None)
    encoded = b64encode(photo.image_data).decode("ascii")
    return ProfilePhotoOut(data_url=f"data:{photo.content_type};base64,{encoded}")


@router.get("/auth/profile-photo", response_model=ProfilePhotoOut)
def get_profile_photo(user: CurrentUser, db: DbSession, response: Response) -> ProfilePhotoOut:
    response.headers["Cache-Control"] = "private, no-store"
    return photo_out(db.get(UserProfilePhoto, user.id))


@router.put("/auth/profile-photo", response_model=ProfilePhotoOut)
async def put_profile_photo(user: CurrentUser, db: DbSession, photo: UploadFile = File(...)) -> ProfilePhotoOut:
    data = await photo.read(MAX_PROFILE_PHOTO_BYTES + 1)
    if len(data) > MAX_PROFILE_PHOTO_BYTES:
        raise HTTPException(413, "La foto no puede superar los 2 MB")
    content_type = photo_type(data)
    if content_type is None:
        raise HTTPException(422, "Usa una imagen PNG, JPEG o WebP")
    item = db.get(UserProfilePhoto, user.id)
    if item is None:
        item = UserProfilePhoto(user_id=user.id, content_type=content_type, image_data=data)
        db.add(item)
    else:
        item.content_type = content_type
        item.image_data = data
    db.commit()
    return photo_out(item)


@router.delete("/auth/profile-photo", status_code=204)
def delete_profile_photo(user: CurrentUser, db: DbSession) -> None:
    item = db.get(UserProfilePhoto, user.id)
    if item is not None:
        db.delete(item)
        db.commit()


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
