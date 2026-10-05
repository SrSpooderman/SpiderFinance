from fastapi import APIRouter, File, Response, UploadFile

from app.http.dependencies import CurrentUser, DbSession
from app.modules.identity.schemas import LoginIn, PasswordChangeIn, ProfilePhotoOut, RegisterIn, SettingsOut, SettingsPatch, TokenOut, UserOut
from app.core.config import settings
from app.modules.identity.application import Identity
from app.modules.identity.domain import MAX_PROFILE_PHOTO_BYTES
from app.modules.identity.infrastructure import CoreCredentials, SqlIdentityStore

router = APIRouter(tags=["auth"])


def identity(db: DbSession) -> Identity:
    return Identity(SqlIdentityStore(db), CoreCredentials())


@router.get("/auth/config")
def auth_config() -> dict[str, bool]:
    return {"registration_enabled": settings.registration_enabled}


@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: DbSession):
    return identity(db).register(str(data.email), data.password, settings.registration_enabled)


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
