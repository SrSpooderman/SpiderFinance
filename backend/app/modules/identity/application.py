"""Identity use cases, including admin user management."""

from base64 import b64encode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.modules.errors import UseCaseError
from app.modules.identity.domain import MAX_PROFILE_PHOTO_BYTES, photo_type
from app.modules.identity.ports import Credentials, IdentityStore


class Identity:
    def __init__(self, store: IdentityStore, credentials: Credentials):
        self.store = store
        self.credentials = credentials

    def register(self, email: str, password: str, enabled: bool) -> dict:
        if not enabled:
            raise UseCaseError(403, "El registro está desactivado")
        email = email.lower()
        if self.store.user_by_email(email):
            raise UseCaseError(409, "Ya existe una cuenta con este correo")
        user = self.store.create_user(email, self.credentials.hash(password))
        return {"access_token": self.credentials.token(user["id"], user["auth_version"])}

    def login(self, email: str, password: str) -> dict:
        user = self.store.user_by_email(email.lower())
        if user is None or not self.credentials.verify(password, user["password_hash"]):
            raise UseCaseError(401, "Credenciales incorrectas")
        return {"access_token": self.credentials.token(user["id"], user["auth_version"])}

    def user(self, user_id: int) -> dict:
        item = self.store.user(user_id)
        if item is None:
            raise UseCaseError(404, "Usuario no encontrado")
        return item

    def change_password(self, user_id: int, current: str, new: str) -> dict:
        user = self.user(user_id)
        if not self.credentials.verify(current, user["password_hash"]):
            raise UseCaseError(400, "La contraseña actual no es correcta")
        if new == current:
            raise UseCaseError(400, "La nueva contraseña debe ser diferente")
        user = self.store.change_password(user_id, self.credentials.hash(new), user["password_hash"])
        return {"access_token": self.credentials.token(user_id, user["auth_version"])}

    def photo(self, user_id: int) -> dict:
        item = self.store.photo(user_id)
        if item is None:
            return {"data_url": None}
        encoded = b64encode(item["image_data"]).decode("ascii")
        return {"data_url": f"data:{item['content_type']};base64,{encoded}"}

    def save_photo(self, user_id: int, data: bytes) -> dict:
        if len(data) > MAX_PROFILE_PHOTO_BYTES:
            raise UseCaseError(413, "La foto no puede superar los 2 MB")
        content_type = photo_type(data)
        if content_type is None:
            raise UseCaseError(422, "Usa una imagen PNG, JPEG o WebP")
        self.store.save_photo(user_id, content_type, data)
        return self.photo(user_id)

    def delete_photo(self, user_id: int) -> None:
        self.store.delete_photo(user_id)

    def settings(self, user_id: int) -> dict:
        return self.store.settings(user_id)

    def update_settings(self, user_id: int, changes: dict) -> dict:
        if any(value is None for value in changes.values()):
            raise UseCaseError(422, "Los ajustes no pueden ser nulos")
        if "timezone" in changes:
            try:
                ZoneInfo(changes["timezone"])
            except ZoneInfoNotFoundError:
                raise UseCaseError(422, "Zona horaria desconocida") from None
        return self.store.update_settings(user_id, changes)

    def users(self) -> list[dict]:
        return self.store.users()
