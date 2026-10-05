"""Identity adapters using existing mappings and password/JWT functions."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_token, hash_password, verify_password
from app.infrastructure.models import Category, IdentityActionToken, IdentityMailThrottle, User, UserProfilePhoto, UserSettings
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

    def change_password(self, user_id: int, password_hash: str, expected_hash: str) -> dict:
        user = self.session.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
        if user.password_hash != expected_hash:
            self.session.rollback()
            raise UseCaseError(409, "La contraseña ha cambiado; inicia sesión de nuevo")
        user.password_hash = password_hash
        user.auth_version += 1
        self.session.execute(update(IdentityActionToken).where(IdentityActionToken.user_id == user_id, IdentityActionToken.used_at.is_(None)).values(used_at=datetime.now(timezone.utc)).execution_options(synchronize_session=False))
        self.session.commit()
        return snapshot(user)

    def allow_mail(self, key_hash: str) -> bool:
        now = datetime.now(timezone.utc)
        item = self.session.get(IdentityMailThrottle, key_hash)
        if item is None:
            self.session.add(IdentityMailThrottle(key_hash=key_hash, window_started_at=now, last_requested_at=now, request_count=1))
            try:
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                return False
            return True
        last = item.last_requested_at.replace(tzinfo=timezone.utc) if item.last_requested_at.tzinfo is None else item.last_requested_at
        started = item.window_started_at.replace(tzinfo=timezone.utc) if item.window_started_at.tzinfo is None else item.window_started_at
        if now - started >= timedelta(days=1):
            item.window_started_at = now
            item.request_count = 0
        if now - last < timedelta(minutes=1) or item.request_count >= 5:
            return False
        item.last_requested_at = now
        item.request_count += 1
        self.session.commit()
        return True

    def issue_action(self, user_id: int, purpose: str, token_hash: str, expires_at: datetime) -> None:
        self.session.scalar(select(User).where(User.id == user_id).with_for_update())
        self.session.execute(update(IdentityActionToken).where(IdentityActionToken.user_id == user_id, IdentityActionToken.purpose == purpose, IdentityActionToken.used_at.is_(None)).values(used_at=datetime.now(timezone.utc)).execution_options(synchronize_session=False))
        self.session.add(IdentityActionToken(user_id=user_id, purpose=purpose, token_hash=token_hash, expires_at=expires_at))
        self.session.commit()

    def finish_action(self, token_hash: str, purpose: str, password_hash: str | None = None) -> dict:
        now = datetime.now(timezone.utc)
        action = self.session.scalar(select(IdentityActionToken).where(IdentityActionToken.token_hash == token_hash, IdentityActionToken.purpose == purpose))
        if action is None:
            raise UseCaseError(400, "El enlace no es válido o ha caducado")
        self.session.scalar(select(User).where(User.id == action.user_id).with_for_update())
        result = self.session.execute(update(IdentityActionToken).where(
            IdentityActionToken.token_hash == token_hash,
            IdentityActionToken.purpose == purpose,
            IdentityActionToken.used_at.is_(None),
            IdentityActionToken.expires_at > now,
        ).values(used_at=now).returning(IdentityActionToken.user_id).execution_options(synchronize_session=False))
        user_id = result.scalar_one_or_none()
        if user_id is None:
            self.session.rollback()
            raise UseCaseError(400, "El enlace no es válido o ha caducado")
        user = self.session.get(User, user_id)
        if purpose in {"verify", "invite"}:
            user.email_verified_at = now
        if password_hash is not None:
            user.password_hash = password_hash
            user.auth_version += 1
            self.session.execute(update(IdentityActionToken).where(IdentityActionToken.user_id == user_id, IdentityActionToken.used_at.is_(None)).values(used_at=now).execution_options(synchronize_session=False))
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
