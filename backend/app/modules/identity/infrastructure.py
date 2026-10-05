"""Identity adapters using existing mappings and password/JWT functions."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_token, hash_password, verify_password
from app.infrastructure.models import Category, User, UserProfilePhoto, UserSettings
from app.modules.errors import UseCaseError
from app.modules.identity.domain import DEFAULT_CATEGORIES
from app.infrastructure.snapshot import snapshot


class CoreCredentials:
    def hash(self, password: str) -> str:
        return hash_password(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return verify_password(password, password_hash)

    def token(self, user_id: int, auth_version: int) -> str:
        return create_token(user_id, auth_version)


class SqlIdentityStore:
    def __init__(self, session: Session):
        self.session = session

    def user_by_email(self, email: str) -> dict | None:
        item = self.session.scalar(select(User).where(User.email == email))
        return snapshot(item) if item else None

    def user(self, user_id: int) -> dict | None:
        item = self.session.get(User, user_id)
        return snapshot(item) if item else None

    def users(self) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(User).order_by(User.id))]

    def create_user(self, email: str, password_hash: str) -> dict:
        user = User(email=email.lower(), password_hash=password_hash)
        self.session.add(user)
        try:
            self.session.flush()
            self.session.add(UserSettings(user_id=user.id))
            self.session.add_all(Category(user_id=user.id, name=name) for name in DEFAULT_CATEGORIES)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise UseCaseError(409, "Ya existe una cuenta con este correo") from None
        self.session.refresh(user)
        return snapshot(user)

    def change_password(self, user_id: int, password_hash: str) -> dict:
        user = self.session.get(User, user_id)
        user.password_hash = password_hash
        user.auth_version += 1
        self.session.commit()
        return snapshot(user)

    def photo(self, user_id: int) -> dict | None:
        item = self.session.get(UserProfilePhoto, user_id)
        return snapshot(item) if item else None

    def save_photo(self, user_id: int, content_type: str, data: bytes) -> dict:
        item = self.session.get(UserProfilePhoto, user_id)
        if item is None:
            item = UserProfilePhoto(user_id=user_id, content_type=content_type, image_data=data)
            self.session.add(item)
        else:
            item.content_type = content_type
            item.image_data = data
        self.session.commit()
        return snapshot(item)

    def delete_photo(self, user_id: int) -> None:
        item = self.session.get(UserProfilePhoto, user_id)
        if item is not None:
            self.session.delete(item)
            self.session.commit()

    def settings(self, user_id: int) -> dict:
        return snapshot(self.session.get(UserSettings, user_id))

    def update_settings(self, user_id: int, changes: dict) -> dict:
        item = self.session.get(UserSettings, user_id)
        for key, value in changes.items():
            setattr(item, key, value)
        self.session.commit()
        return snapshot(item)
